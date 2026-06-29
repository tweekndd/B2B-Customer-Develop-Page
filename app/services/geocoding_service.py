"""
Geocoding 地理编码服务（V3.2.4 新增）
使用 Nominatim (OpenStreetMap) 将客户国家转换为经纬度坐标，
为地图可视化提供数据基础。

注意：Customer 模型目前无 city 字段，仅使用 country 进行地理编码。
"""
import logging
from typing import Dict

from sqlalchemy.orm import Session
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from app.database import Customer

logger = logging.getLogger(__name__)

# ── 全局 Geocoder 实例 ──
_geolocator = Nominatim(user_agent="AITradeCustomerAnalyzer/3.2.4")
_geocode = RateLimiter(_geolocator.geocode, min_delay_seconds=1.0, max_retries=2)


def geocode_customer(db: Session, customer: Customer) -> bool:
    """
    对单个客户进行地理编码。
    如果 customer.geocode_status == "done" 则跳过。
    由于 Customer 模型目前没有 city 字段，仅使用 country 进行查询。

    Args:
        db: 数据库会话
        customer: 客户对象

    Returns:
        True 表示成功，False 表示失败或跳过
    """
    if customer.geocode_status == "done":
        return False  # 已编码，跳过

    # 构造查询字符串：仅使用 country（模型无 city 字段）
    query_parts = []
    if customer.country and customer.country.strip():
        query_parts.append(customer.country.strip())

    if not query_parts:
        # 无可用地址信息，标记为失败
        customer.geocode_status = "failed"
        db.commit()
        logger.warning("客户 %s (ID=%s) 缺少国家信息，无法编码", customer.company_name, customer.id)
        return False

    query = ", ".join(query_parts)
    logger.info("正在地理编码: 客户=%s, 查询=%s", customer.company_name, query)

    try:
        location = _geocode(query)
        if location:
            customer.latitude = location.latitude
            customer.longitude = location.longitude
            customer.geocode_status = "done"
            db.commit()
            logger.info(
                "地理编码成功: %s -> (%.4f, %.4f)",
                customer.company_name, location.latitude, location.longitude
            )
            return True
        else:
            customer.geocode_status = "failed"
            db.commit()
            logger.warning("地理编码无结果: %s, 查询=%s", customer.company_name, query)
            return False
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        customer.geocode_status = "failed"
        db.commit()
        logger.error("地理编码异常: %s, 查询=%s, 错误=%s", customer.company_name, query, e)
        return False


def batch_geocode(db: Session) -> Dict[str, int]:
    """
    批量地理编码：处理所有 geocode_status != "done" 的客户。
    逐个调用 geocode_customer，受 RateLimiter 控制频率（1次/秒）。

    Args:
        db: 数据库会话

    Returns:
        统计字典: {total: N, succeeded: N, failed: N, skipped: N}
    """
    pending = (
        db.query(Customer)
        .filter(Customer.geocode_status != "done")
        .all()
    )

    total = len(pending)
    succeeded = 0
    failed = 0
    skipped = 0

    logger.info("批量地理编码启动: 共 %s 个待处理客户", total)

    for customer in pending:
        # 空国家直接跳过
        if not customer.country or not customer.country.strip():
            customer.geocode_status = "failed"
            db.commit()
            skipped += 1
            continue

        result = geocode_customer(db, customer)
        if result:
            succeeded += 1
        else:
            if customer.geocode_status == "done":
                skipped += 1
            else:
                failed += 1

        # 注意：geopy 的 RateLimiter 已控制请求间隔，此处不需要额外 sleep

    logger.info(
        "批量地理编码完成: 总计=%s, 成功=%s, 失败=%s, 跳过=%s",
        total, succeeded, failed, skipped
    )

    return {
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
    }
