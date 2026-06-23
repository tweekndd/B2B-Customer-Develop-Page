"""
客户发现 API 路由
包含搜索任务管理、关键词扩展、相似客户扩展、SSE 实时流
从 routes.py 拆分（V2.8 重构）
V3.1.1 新增 SSE 端点取代轮询
"""
import json
import datetime
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db, Customer, SearchTask, SessionLocal
from app.services.search_task_service import run_search_task, request_task_stop, get_paused_tasks, resume_paused_task
from app.services.keyword_expander import expand_keywords
from app.services.deduplication import find_existing_customer

router = APIRouter(tags=["discovery"])


async def _run_task_wrapper(task_id: int):
    """异步包装器，确保任务异常不影响主进程"""
    try:
        await run_search_task(task_id)
    except Exception as e:
        print(f"搜索任务 {task_id} 异常退出: {str(e)[:200]}")


# ═══════════════════════════════════════════
# 关键词扩展
# ═══════════════════════════════════════════

@router.post("/discovery/expand-keywords")
async def api_expand_keywords(
    keyword: str = Query(..., description="需要扩展的基础关键词"),
    country: str = Query("", description="目标国家（可选，传入后AI会用该国家的本地语言扩展关键词）"),
):
    """AI扩展关键词（支持多语言：传入 country 会自动使用该国语言）"""
    expanded = await expand_keywords(keyword, country=country)
    if not expanded:
        expanded = [keyword]
    return {"original_keyword": keyword, "expanded_keywords": expanded, "country": country}


# ═══════════════════════════════════════════
# 搜索任务管理
# ═══════════════════════════════════════════

@router.post("/discovery/search-task")
async def create_search_task(
    country: str = Query(..., description="搜索国家"),
    keyword: str = Query(..., description="搜索关键词"),
    depth: int = Query(50, description="搜索深度"),
    db: Session = Depends(get_db),
):
    """创建新的搜索发现任务"""
    task = SearchTask(
        country=country,
        keyword=keyword,
        search_depth=depth,
        status="Pending",
        created_at=datetime.datetime.utcnow(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 异步启动任务
    loop = asyncio.get_event_loop()
    loop.create_task(_run_task_wrapper(task.id))

    return {"message": "搜索任务已创建", "task_id": task.id}


@router.get("/discovery/tasks")
def list_search_tasks(db: Session = Depends(get_db)):
    """获取所有搜索任务列表"""
    tasks = db.query(SearchTask).order_by(SearchTask.created_at.desc()).all()
    result = []
    for t in tasks:
        expanded = []
        if t.expanded_keywords:
            try:
                expanded = json.loads(t.expanded_keywords)
            except (json.JSONDecodeError, TypeError):
                pass
        result.append({
            "id": t.id,
            "country": t.country,
            "keyword": t.keyword,
            "expanded_keywords": expanded,
            "search_depth": t.search_depth,
            "status": t.status,
            "found_websites": t.found_websites or 0,
            "analyzed_companies": t.analyzed_companies or 0,
            "new_companies": t.new_companies or 0,
            "current_keyword_index": t.current_keyword_index or 0,
            "error_message": t.error_message,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "finished_at": t.finished_at.isoformat() if t.finished_at else None,
            "task_log": t.task_log or "",
        })

    # 标记当前活跃任务（优先 Running，其次 Pending）
    active_task_id = None
    for t in tasks:
        if t.status == "Running":
            active_task_id = t.id
            break
    if active_task_id is None:
        for t in tasks:
            if t.status == "Pending":
                active_task_id = t.id
                break

    return {"tasks": result, "total": len(result), "active_task_id": active_task_id}


@router.post("/discovery/tasks/{task_id}/pause")
def pause_task(task_id: int, db: Session = Depends(get_db)):
    """暂停指定的搜索任务"""
    request_task_stop(task_id)
    return {"message": f"正在停止搜索任务 #{task_id}"}


@router.post("/discovery/tasks/{task_id}/resume")
def resume_task(task_id: int, db: Session = Depends(get_db)):
    """恢复暂停的搜索任务（断点续跑）"""
    success = resume_paused_task(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="任务不存在或无法恢复")
    # 重新启动
    loop = asyncio.get_event_loop()
    loop.create_task(_run_task_wrapper(task_id))
    return {"message": "任务已恢复", "task_id": task_id}


@router.delete("/discovery/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    """删除搜索任务"""
    task = db.query(SearchTask).filter(SearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    db.delete(task)
    db.commit()
    return {"message": "删除成功"}


@router.get("/discovery/paused-tasks")
def list_paused_tasks(db: Session = Depends(get_db)):
    """获取所有暂停的任务（用于断点续跑）"""
    tasks = get_paused_tasks(db)
    result = []
    for t in tasks:
        result.append({
            "id": t.id,
            "country": t.country,
            "keyword": t.keyword,
            "status": t.status,
            "current_keyword_index": t.current_keyword_index or 0,
        })
    return {"paused_tasks": result}


# ═══════════════════════════════════════════
# SSE 实时任务状态流（V3.1.1 新增，替代轮询）
# ═══════════════════════════════════════════

@router.get("/discovery/task-stream/{task_id}")
async def task_stream(task_id: int, request: Request, db: Session = Depends(get_db)):
    """SSE 端点：推送搜索任务实时进度，任务结束时自动发送 done 事件后关闭连接。"""
    task = db.query(SearchTask).filter(SearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    async def _stream_events():
        last_status = None
        last_kw_index = -1
        try:
            while True:
                # 检查客户端是否断开
                if await request.is_disconnected():
                    break

                db = SessionLocal()
                try:
                    task = db.query(SearchTask).filter(SearchTask.id == task_id).first()
                    if not task:
                        yield f"event: error\ndata: {json.dumps({'detail':'任务不存在'})}\n\n"
                        break

                    # 构建精简状态数据
                    expanded = []
                    if task.expanded_keywords:
                        try:
                            expanded = json.loads(task.expanded_keywords)
                        except (json.JSONDecodeError, TypeError):
                            pass

                    status = task.status
                    kw_index = task.current_keyword_index or 0

                    # 状态有变化才推送
                    changed = (status != last_status) or (kw_index != last_kw_index)

                    if changed:
                        payload = {
                            "id": task.id,
                            "status": status,
                            "found_websites": task.found_websites or 0,
                            "analyzed_companies": task.analyzed_companies or 0,
                            "new_companies": task.new_companies or 0,
                            "current_keyword_index": kw_index,
                            "expanded_keywords": expanded,
                            "error_message": task.error_message,
                            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
                            "keyword": task.keyword,
                            "country": task.country,
                            "search_depth": task.search_depth,
                        }
                        last_status = status
                        last_kw_index = kw_index

                        yield f"event: progress\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

                    # 终端状态 - 发送 done 后退出
                    if status in ("Completed", "Failed", "Paused"):
                        yield f"event: done\ndata: {json.dumps({'id': task.id, 'status': status}, ensure_ascii=False)}\n\n"
                        break
                finally:
                    db.close()

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        _stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════════════════════════════════
# 发现结果列表
# ═══════════════════════════════════════════

@router.get("/discovery/discovered-customers")
def list_discovered_customers(
    search: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None, description="按发现关键词筛选"),
    sort_by_score: Optional[str] = Query("desc"),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(50, ge=10, le=200, description="每页条数（10-200）"),
    db: Session = Depends(get_db),
):
    """获取通过Google发现的公司列表（支持分页）"""
    query = db.query(Customer).filter(Customer.discovery_source == "Google")
    if search:
        query = query.filter(Customer.company_name.ilike(f"%{search}%"))
    if country:
        query = query.filter(Customer.country == country)
    if priority:
        query = query.filter(Customer.priority == priority.upper())
    if keyword:
        query = query.filter(Customer.discovery_keyword.ilike(f"%{keyword}%"))
    if sort_by_score == "asc":
        query = query.order_by(Customer.total_score.asc().nullslast())
    else:
        query = query.order_by(Customer.total_score.desc().nullslast())

    total_count = query.count()
    offset_val = (page - 1) * page_size
    customers = query.offset(offset_val).limit(page_size).all()

    all_countries = db.query(Customer.country).distinct().filter(
        Customer.country.isnot(None), Customer.country != "",
        Customer.discovery_source == "Google",
    ).order_by(Customer.country).all()
    country_list = [c[0] for c in all_countries if c[0]]

    all_keywords = db.query(Customer.discovery_keyword).distinct().filter(
        Customer.discovery_keyword.isnot(None), Customer.discovery_keyword != "",
        Customer.discovery_source == "Google",
    ).all()
    keyword_list = list(set(k[0] for k in all_keywords if k[0]))

    # 复用 customers 模块的邮箱解析
    def _get_emails(customer):
        if not customer.emails:
            return []
        try:
            return json.loads(customer.emails)
        except (json.JSONDecodeError, TypeError):
            return [e.strip() for e in customer.emails.split(",") if e.strip()]

    result = []
    for c in customers:
        emails = _get_emails(c)
        result.append({
            "id": c.id,
            "company_name": c.company_name,
            "website": c.website or "",
            "country": c.country or "",
            "email_count": len(emails),
            "total_score": c.total_score,
            "priority": c.priority or "-",
            "discovery_keyword": c.discovery_keyword or "",
            "ai_summary": c.ai_summary or "",
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    return {
        "customers": result,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total_count + page_size - 1) // page_size),
        "countries": country_list,
        "keywords": keyword_list,
    }


# ═══════════════════════════════════════════
# V2.5：相似客户扩展（种子客户）
# ═══════════════════════════════════════════

@router.post("/discovery/similar-companies")
async def api_find_similar_companies(
    company_url: str = Query(..., description="目标公司网址"),
    target_country: str = Query(..., description="目标国家"),
    top_n: int = Query(50, ge=10, le=100, description="返回结果数量"),
):
    """基于公司网址寻找相似客户"""
    from app.services.similar_company_finder import find_similar_companies

    result = await find_similar_companies(company_url, target_country, top_n=top_n)
    return result
