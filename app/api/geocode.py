"""
Geocoding 地理编码 API 路由（V3.2.4 新增）
提供批量/单个客户地理编码触发器，以及地图数据获取接口。
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db, Customer
from app.services.geocoding_service import geocode_customer, batch_geocode

logger = logging.getLogger(__name__)

router = APIRouter(tags=["geocode"])


@router.post("/customers/geocode/batch")
def trigger_batch_geocode(db: Session = Depends(get_db)):
    """
    触发批量地理编码任务。
    同步执行（桌面应用场景），返回处理统计。
    """
    try:
        stats = batch_geocode(db)
        return {
            "status": "completed",
            "message": "批量地理编码任务已完成",
            "stats": stats,
        }
    except Exception as e:
        logger.error("批量地理编码失败: %s", e)
        raise HTTPException(status_code=500, detail=f"批量地理编码失败: {str(e)}")


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
    db: Session = Depends(get_db),
):
    """
    获取地图可视化数据。
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

    customers = query.all()

    results = []
    for c in customers:
        results.append({
            "id": c.id,
            "name": c.company_name,
            "country": c.country,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "total_score": c.total_score,
            "status": c.status,
            "priority": c.priority,
        })

    # 统计信息
    total_count = db.query(Customer).count()
    geocoded_count = len(results)
    pending_count = total_count - geocoded_count
    countries = set()
    for r in results:
        if r.get("country"):
            countries.add(r["country"])

    return {
        "total": len(results),
        "customers": results,
        "stats": {
            "total": total_count,
            "geocoded": geocoded_count,
            "pending": pending_count,
            "countries": len(countries),
        },
    }
