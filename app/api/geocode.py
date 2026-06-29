"""
Geocoding 地理编码 API 路由（V3.2.4 新增）
提供批量/单个客户地理编码触发器，以及地图数据获取接口。
"""
import logging
import uuid
from typing import Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db, Customer
from app.services.geocoding_service import geocode_customer, batch_geocode

logger = logging.getLogger(__name__)

router = APIRouter(tags=["geocode"])

# 后台任务状态存储
_batch_tasks: Dict[str, dict] = {}


def _run_batch_geocode(task_id: str):
    """后台执行批量地理编码"""
    _batch_tasks[task_id] = {"status": "running", "stats": None, "error": None}
    try:
        db = SessionLocal()
        stats = batch_geocode(db)
        db.close()
        _batch_tasks[task_id]["status"] = "completed"
        _batch_tasks[task_id]["stats"] = stats
    except Exception as e:
        logger.error("批量地理编码后台任务失败", exc_info=True)
        _batch_tasks[task_id]["status"] = "failed"
        _batch_tasks[task_id]["error"] = str(e)


@router.post("/customers/geocode/batch")
def trigger_batch_geocode(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    触发批量地理编码任务（异步后台执行）。
    返回 task_id 供前端轮询查询进度。
    """
    task_id = str(uuid.uuid4())[:8]
    _batch_tasks[task_id] = {"status": "pending", "stats": None, "error": None}
    background_tasks.add_task(_run_batch_geocode, task_id)
    return {"status": "accepted", "task_id": task_id, "message": "批量地理编码任务已提交，请稍后查看结果"}


@router.get("/customers/geocode/status/{task_id}")
def get_geocode_status(task_id: str):
    """查询批量地理编码任务状态"""
    task = _batch_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"task_id": task_id, **task}


@router.post("/customers/{customer_id}/geocode")
def trigger_single_geocode(customer_id: int, db: Session = Depends(get_db)):
    """
    对单个客户进行地理编码。
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="客户不存在")

    result = geocode_customer(db, customer)

    if result:
        return {
            "status": "ok",
            "customer_id": customer_id,
            "latitude": customer.latitude,
            "longitude": customer.longitude,
        }
    else:
        if customer.geocode_status == "done":
            return {
                "status": "skipped",
                "customer_id": customer_id,
                "message": "该客户已完成地理编码",
            }
        else:
            return {
                "status": "failed",
                "customer_id": customer_id,
                "message": "地理编码失败（无结果或发生错误）",
            }


@router.get("/customers/map")
def get_map_data(
    country: Optional[str] = Query(None, description="按国家精确过滤（URL解码后）"),
    limit: int = Query(5000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    获取地图可视化数据（支持分页）。
    只返回 geocode_status="done" 且经纬度不为空的客户。
    支持按国家过滤。
    """
    query = db.query(Customer).filter(
        Customer.geocode_status == "done",
        Customer.latitude.isnot(None),
        Customer.longitude.isnot(None),
    )

    if country:
        query = query.filter(Customer.country == country)

    total_filtered = query.count()
    customers = query.offset(offset).limit(limit).all()

    results = []
    countries_set = set()
    for c in customers:
        results.append({
            "id": c.id,
            "name": c.company_name,
            "country": c.country,
            "city": c.city or "",
            "latitude": c.latitude,
            "longitude": c.longitude,
            "total_score": c.total_score,
            "status": c.status,
            "priority": c.priority,
        })
        if c.country:
            countries_set.add(c.country)

    total_all = db.query(Customer).count()
    geocoded_count = total_filtered
    pending_count = total_all - geocoded_count

    return {
        "total": total_filtered,
        "customers": results,
        "stats": {
            "total": total_all,
            "geocoded": geocoded_count,
            "pending": pending_count,
            "countries": len(countries_set),
        },
    }
