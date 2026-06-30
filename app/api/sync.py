"""
数据同步 API 路由
支持多设备间通过网盘/USB 导出导入客户数据
V3.2.6: 新增备份/恢复功能（网页端一键操作）
从 routes.py 拆分（V2.8 重构）
"""
import datetime
import json
import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db, Customer, SearchTask, SearchCache, WebsiteCache, AnalysisCache
from app.services.deduplication import find_existing_customer

router = APIRouter(tags=["sync"])

# ─── 备份目录配置 ───
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKUP_DIR = PROJECT_ROOT / "backups"


def _ensure_backup_dir():
    """确保备份目录存在"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def _get_db_path():
    """获取数据库文件路径"""
    # 默认数据库是 app/customers.db 或环境变量指定的其他路径
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if db_url and db_url.startswith("sqlite:///"):
        # 提取 SQLite 文件路径
        rel_path = db_url[10:]  # 去掉 "sqlite:///"
        return PROJECT_ROOT / rel_path
    return PROJECT_ROOT / "app" / "customers.db"


@router.get("/sync/export")
def export_all_data(db: Session = Depends(get_db)):
    """
    导出全部数据为 JSON
    用于多设备间数据同步（通过网盘/USB 传输）
    """
    # 客户数据
    customers = db.query(Customer).order_by(Customer.id).all()
    customers_data = []
    for c in customers:
        customers_data.append({
            "id": c.id,
            "company_name": c.company_name,
            "website": c.website,
            "country": c.country,
            "discovery_source": c.discovery_source,
            "discovery_keyword": c.discovery_keyword,
            "first_found_at": c.first_found_at.isoformat() if c.first_found_at else None,
            "emails": c.emails,
            "website_text": c.website_text,
            "positive_keywords": c.positive_keywords,
            "negative_keywords": c.negative_keywords,
            "industry_score": c.industry_score,
            "project_score": c.project_score,
            "company_type_score": c.company_type_score,
            "country_score": c.country_score,
            "contact_score": c.contact_score,
            "total_score": c.total_score,
            "priority": c.priority,
            "company_type": c.company_type,
            "ai_summary": c.ai_summary,
            "sales_hook": c.sales_hook,
            "target_position": c.target_position,
            "identified_projects": c.identified_projects,
            "ai_raw_json": c.ai_raw_json,
            "status": c.status,
            "follow_up_date": c.follow_up_date.isoformat() if c.follow_up_date else None,
            "notes": c.notes,
            "scrape_status": c.scrape_status,
            "ai_status": c.ai_status,
            "fail_reason": c.fail_reason,
            "star_rating": c.star_rating,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "analyzed_at": c.analyzed_at.isoformat() if c.analyzed_at else None,
        })

    # 搜索任务
    tasks = db.query(SearchTask).order_by(SearchTask.id).all()
    tasks_data = []
    for t in tasks:
        tasks_data.append({
            "id": t.id,
            "country": t.country,
            "keyword": t.keyword,
            "expanded_keywords": t.expanded_keywords,
            "search_depth": t.search_depth,
            "status": t.status,
            "found_websites": t.found_websites,
            "analyzed_companies": t.analyzed_companies,
            "new_companies": t.new_companies,
            "current_keyword_index": t.current_keyword_index,
            "error_message": t.error_message,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "finished_at": t.finished_at.isoformat() if t.finished_at else None,
            "task_log": t.task_log,
        })

    # 缓存数据（提升同步后搜索效率）
    search_cache = db.query(SearchCache).order_by(SearchCache.id).all()
    search_cache_data = []
    for s in search_cache:
        search_cache_data.append({
            "keyword": s.keyword,
            "country": s.country,
            "website": s.website,
            "title": s.title,
            "snippet": s.snippet,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })

    website_cache = db.query(WebsiteCache).order_by(WebsiteCache.id).all()
    website_cache_data = []
    for w in website_cache:
        website_cache_data.append({
            "website": w.website,
            "content": w.content,
            "content_hash": w.content_hash,
            "last_crawled": w.last_crawled.isoformat() if w.last_crawled else None,
        })

    analysis_cache = db.query(AnalysisCache).order_by(AnalysisCache.id).all()
    analysis_cache_data = []
    for a in analysis_cache:
        analysis_cache_data.append({
            "website": a.website,
            "content_hash": a.content_hash,
            "company_type": a.company_type,
            "summary": a.summary,
            "sales_hook": a.sales_hook,
            "target_position": a.target_position,
            "analysis_reason": a.analysis_reason,
            "identified_projects": a.identified_projects,
            "raw_json": a.raw_json,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })

    return {
        "exported_at": datetime.datetime.utcnow().isoformat(),
        "version": "2.6",
        "stats": {
            "customers": len(customers_data),
            "search_tasks": len(tasks_data),
            "search_cache": len(search_cache_data),
            "website_cache": len(website_cache_data),
            "analysis_cache": len(analysis_cache_data),
        },
        "data": {
            "customers": customers_data,
            "search_tasks": tasks_data,
            "search_cache": search_cache_data,
            "website_cache": website_cache_data,
            "analysis_cache": analysis_cache_data,
        },
    }


@router.post("/sync/import")
def import_sync_data(
    data: dict,
    db: Session = Depends(get_db),
):
    """
    导入同步数据（JSON 格式，由 /sync/export 生成）
    自动去重：已存在的客户按域名/公司名合并，不重复创建
    """
    imported = data.get("data", {})
    if not imported:
        raise HTTPException(status_code=400, detail="数据为空")

    # ── 1. 导入 search_tasks（按业务键去重，不依赖源 ID） ──
    task_count = 0
    for t_data in imported.get("search_tasks", []):
        existing = db.query(SearchTask).filter(
            SearchTask.country == t_data.get("country", ""),
            SearchTask.keyword == t_data.get("keyword", ""),
        ).first()
        if existing:
            continue
        task = SearchTask(
            country=t_data.get("country", ""),
            keyword=t_data.get("keyword", ""),
            expanded_keywords=t_data.get("expanded_keywords"),
            search_depth=t_data.get("search_depth", 50),
            status=t_data.get("status", "Pending"),
            found_websites=t_data.get("found_websites", 0),
            analyzed_companies=t_data.get("analyzed_companies", 0),
            new_companies=t_data.get("new_companies", 0),
            current_keyword_index=t_data.get("current_keyword_index", 0),
            error_message=t_data.get("error_message"),
            task_log=t_data.get("task_log"),
        )
        if t_data.get("created_at"):
            task.created_at = datetime.datetime.fromisoformat(t_data["created_at"])
        if t_data.get("finished_at"):
            task.finished_at = datetime.datetime.fromisoformat(t_data["finished_at"])
        db.add(task)
        task_count += 1

    # ── 2. 导入 customers（自动去重） ──
    cust_count = 0
    skip_count = 0
    for c_data in imported.get("customers", []):
        existing = find_existing_customer(db, c_data.get("website", ""), c_data.get("company_name", ""))
        if existing:
            skip_count += 1
            continue

        customer = Customer(
            company_name=c_data.get("company_name", ""),
            website=c_data.get("website", ""),
            country=c_data.get("country", ""),
            discovery_source=c_data.get("discovery_source"),
            discovery_keyword=c_data.get("discovery_keyword"),
            emails=c_data.get("emails"),
            website_text=c_data.get("website_text"),
            positive_keywords=c_data.get("positive_keywords"),
            negative_keywords=c_data.get("negative_keywords"),
            industry_score=c_data.get("industry_score"),
            project_score=c_data.get("project_score"),
            company_type_score=c_data.get("company_type_score"),
            country_score=c_data.get("country_score"),
            contact_score=c_data.get("contact_score"),
            total_score=c_data.get("total_score"),
            priority=c_data.get("priority"),
            company_type=c_data.get("company_type"),
            ai_summary=c_data.get("ai_summary"),
            sales_hook=c_data.get("sales_hook"),
            target_position=c_data.get("target_position"),
            identified_projects=c_data.get("identified_projects"),
            ai_raw_json=c_data.get("ai_raw_json"),
            status=c_data.get("status", "待联系"),
            follow_up_date=c_data.get("follow_up_date"),
            notes=c_data.get("notes"),
            scrape_status=c_data.get("scrape_status"),
            ai_status=c_data.get("ai_status"),
            fail_reason=c_data.get("fail_reason"),
            star_rating=c_data.get("star_rating", 0),
        )
        if c_data.get("first_found_at"):
            customer.first_found_at = datetime.datetime.fromisoformat(c_data["first_found_at"])
        if c_data.get("created_at"):
            customer.created_at = datetime.datetime.fromisoformat(c_data["created_at"])
        if c_data.get("analyzed_at"):
            customer.analyzed_at = datetime.datetime.fromisoformat(c_data["analyzed_at"])

        db.add(customer)
        cust_count += 1

    # ── 3. 导入 search_cache（缓存数据，带关键词+国家去重） ──
    sc_count = 0
    seen_sc = set()
    for s_data in imported.get("search_cache", []):
        key = (s_data.get("keyword", ""), s_data.get("country", ""), s_data.get("website", ""))
        if key in seen_sc:
            continue
        seen_sc.add(key)
        existing = db.query(SearchCache).filter(
            SearchCache.keyword == s_data["keyword"],
            SearchCache.country == s_data["country"],
            SearchCache.website == s_data["website"],
        ).first()
        if existing:
            continue
        entry = SearchCache(
            keyword=s_data.get("keyword", ""),
            country=s_data.get("country", ""),
            website=s_data.get("website", ""),
            title=s_data.get("title"),
            snippet=s_data.get("snippet"),
        )
        if s_data.get("created_at"):
            entry.created_at = datetime.datetime.fromisoformat(s_data["created_at"])
        db.add(entry)
        sc_count += 1

    # ── 4. 导入 website_cache ──
    wc_count = 0
    for w_data in imported.get("website_cache", []):
        website = w_data.get("website", "")
        if not website:
            continue
        existing = db.query(WebsiteCache).filter(
            WebsiteCache.website == website
        ).first()
        if existing:
            continue
        entry = WebsiteCache(
            website=website,
            content=w_data.get("content"),
            content_hash=w_data.get("content_hash"),
        )
        if w_data.get("last_crawled"):
            entry.last_crawled = datetime.datetime.fromisoformat(w_data["last_crawled"])
        db.add(entry)
        wc_count += 1

    # ── 5. 导入 analysis_cache ──
    ac_count = 0
    for a_data in imported.get("analysis_cache", []):
        website = a_data.get("website", "")
        if not website:
            continue
        existing = db.query(AnalysisCache).filter(
            AnalysisCache.website == website
        ).first()
        if existing:
            continue
        entry = AnalysisCache(
            website=website,
            content_hash=a_data.get("content_hash"),
            company_type=a_data.get("company_type"),
            summary=a_data.get("summary"),
            sales_hook=a_data.get("sales_hook"),
            target_position=a_data.get("target_position"),
            analysis_reason=a_data.get("analysis_reason"),
            identified_projects=a_data.get("identified_projects"),
            raw_json=a_data.get("raw_json"),
        )
        if a_data.get("created_at"):
            entry.created_at = datetime.datetime.fromisoformat(a_data["created_at"])
        db.add(entry)
        ac_count += 1

    db.commit()

    return {
        "message": "同步完成",
        "imported": {
            "customers": cust_count,
            "customers_skipped": skip_count,
            "search_tasks": task_count,
            "search_cache": sc_count,
            "website_cache": wc_count,
            "analysis_cache": ac_count,
        },
    }


# ═══════════════════════════════════════════════════════════════
# 备份/恢复接口（网页端一键操作）
# ═══════════════════════════════════════════════════════════════

@router.get("/sync/backups")
def list_backups():
    """列出所有数据库备份文件"""
    backup_dir = _ensure_backup_dir()
    backups = []
    for f in sorted(backup_dir.glob("backup_*.db"), key=os.path.getmtime, reverse=True):
        backups.append({
            "name": f.name,
            "size": f.stat().st_size,
            "size_str": _fmt_size(f.stat().st_size),
            "modified": datetime.datetime.fromtimestamp(
                f.stat().st_mtime
            ).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return {"backups": backups, "backup_dir": str(backup_dir)}


@router.post("/sync/backup")
def create_backup():
    """创建数据库备份（带时间戳）"""
    db_path = _get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"数据库文件未找到: {db_path}")

    backup_dir = _ensure_backup_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"backup_{timestamp}.db"

    try:
        shutil.copy2(db_path, backup_file)
    except PermissionError:
        raise HTTPException(status_code=503, detail="数据库文件被占用，请关闭程序后重试")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"备份失败: {e}")

    return {
        "message": "备份成功",
        "file": backup_file.name,
        "size": backup_file.stat().st_size,
        "size_str": _fmt_size(backup_file.stat().st_size),
        "backup_dir": str(backup_dir),
    }


@router.post("/sync/restore")
def restore_backup(name: str = Query(..., description="备份文件名，如 backup_20260101_120000.db")):
    """从备份文件恢复数据库"""
    backup_dir = _ensure_backup_dir()
    backup_file = backup_dir / name

    if not backup_file.exists():
        raise HTTPException(status_code=404, detail=f"备份文件未找到: {name}")

    if not backup_file.is_file() or backup_file.suffix != ".db":
        raise HTTPException(status_code=400, detail="无效的备份文件")

    db_path = _get_db_path()

    # 自动备份当前数据库
    before_backup = db_path.with_suffix(db_path.suffix + ".before_restore.bak")
    try:
        if db_path.exists():
            shutil.copy2(db_path, before_backup)
    except Exception:
        pass  # 自动备份失败不影响恢复

    try:
        shutil.copy2(backup_file, db_path)
    except PermissionError:
        raise HTTPException(status_code=503, detail="数据库文件被占用，请关闭程序后重试")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复失败: {e}")

    return {
        "message": "恢复成功，请重启程序使数据生效",
        "restored_from": name,
        "backup_before": before_backup.name if before_backup.exists() else None,
    }


def _fmt_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes} 字节"
