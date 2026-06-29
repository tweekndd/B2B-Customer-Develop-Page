"""
Geocoding 地理编码服务（V3.2.6 更新）
使用 Nominatim (OpenStreetMap) 将客户城市+国家转换为经纬度坐标，
为地图可视化提供数据基础。

V3.2.6 更新（实际版本号）：
  - 无城市数据时：查询国家中心坐标 + 添加随机抖动，使同国标记在地图上分散
  - 有城市数据时：精确查询 "城市, 国家"，结果可缓存
  - 修复 autoflush=False 导致 GeocodeCache UNIQUE 约束冲突的 bug
"""
import logging
import random
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from app.database import Customer, GeocodeCache

logger = logging.getLogger(__name__)

# ── 全局 Geocoder 实例 ──
_geolocator = Nominatim(user_agent="AITradeCustomerAnalyzer/3.2.6")
_geocode = RateLimiter(_geolocator.geocode, min_delay_seconds=1.0, max_retries=2)

# 无城市数据时的随机抖动范围（度）
# ±0.5° ≈ ±55km，足以在国家级视图区分标记，又不至于偏离国家太远
_JITTER_RANGE = 0.5

# 常见国家中心坐标（latitude, longitude），作为 Nominatim 查不到的兜底
_COUNTRY_CENTERS = {
    "中国": (35.86, 104.19),
    "China": (35.86, 104.19),
    "美国": (37.09, -95.71),
    "United States": (37.09, -95.71),
    "日本": (36.20, 138.25),
    "Japan": (36.20, 138.25),
    "韩国": (35.91, 127.77),
    "South Korea": (35.91, 127.77),
    "德国": (51.17, 10.45),
    "Germany": (51.17, 10.45),
    "英国": (55.38, -3.44),
    "United Kingdom": (55.38, -3.44),
    "法国": (46.60, 1.89),
    "France": (46.60, 1.89),
    "澳大利亚": (-25.27, 133.78),
    "Australia": (-25.27, 133.78),
    "加拿大": (56.13, -106.35),
    "Canada": (56.13, -106.35),
    "印度": (20.59, 78.96),
    "India": (20.59, 78.96),
    "新加坡": (1.35, 103.82),
    "Singapore": (1.35, 103.82),
    "俄罗斯": (61.52, 105.32),
    "Russia": (61.52, 105.32),
    "巴西": (-14.24, -51.93),
    "Brazil": (-14.24, -51.93),
    "意大利": (41.87, 12.57),
    "Italy": (41.87, 12.57),
    "西班牙": (40.46, -3.75),
    "Spain": (40.46, -3.75),
    "荷兰": (52.13, 5.29),
    "Netherlands": (52.13, 5.29),
    "瑞士": (46.82, 8.23),
    "Switzerland": (46.82, 8.23),
    "瑞典": (60.13, 18.64),
    "Sweden": (60.13, 18.64),
    "挪威": (60.47, 8.47),
    "Norway": (60.47, 8.47),
    "丹麦": (56.26, 9.50),
    "Denmark": (56.26, 9.50),
    "芬兰": (61.92, 25.75),
    "Finland": (61.92, 25.75),
    "波兰": (51.92, 19.15),
    "Poland": (51.92, 19.15),
    "沙特阿拉伯": (24.0, 45.0),
    "Saudi Arabia": (24.0, 45.0),
    "阿联酋": (23.42, 53.85),
    "UAE": (23.42, 53.85),
    "United Arab Emirates": (23.42, 53.85),
    "卡塔尔": (25.35, 51.18),
    "Qatar": (25.35, 51.18),
    "阿曼": (21.0, 57.0),
    "Oman": (21.0, 57.0),
    "科威特": (29.31, 47.48),
    "Kuwait": (29.31, 47.48),
    "巴林": (26.07, 50.56),
    "Bahrain": (26.07, 50.56),
    "土耳其": (38.96, 35.24),
    "Turkey": (38.96, 35.24),
    "埃及": (26.82, 30.80),
    "Egypt": (26.82, 30.80),
    "南非": (-30.56, 22.94),
    "South Africa": (-30.56, 22.94),
    "尼日利亚": (9.08, 8.68),
    "Nigeria": (9.08, 8.68),
    "肯尼亚": (-0.02, 37.91),
    "Kenya": (-0.02, 37.91),
    "墨西哥": (23.63, -102.55),
    "Mexico": (23.63, -102.55),
    "阿根廷": (-38.42, -63.62),
    "Argentina": (-38.42, -63.62),
    "智利": (-35.68, -71.54),
    "Chile": (-35.68, -71.54),
    "哥伦比亚": (4.57, -74.30),
    "Colombia": (4.57, -74.30),
    "泰国": (15.87, 100.99),
    "Thailand": (15.87, 100.99),
    "越南": (14.06, 108.28),
    "Vietnam": (14.06, 108.28),
    "印度尼西亚": (-0.79, 113.92),
    "Indonesia": (-0.79, 113.92),
    "马来西亚": (4.21, 101.98),
    "Malaysia": (4.21, 101.98),
    "菲律宾": (12.88, 121.77),
    "Philippines": (12.88, 121.77),
    "巴基斯坦": (30.38, 69.35),
    "Pakistan": (30.38, 69.35),
    "孟加拉国": (23.68, 90.36),
    "Bangladesh": (23.68, 90.36),
}


def _build_query(customer: Customer) -> Optional[str]:
    """
    构建地理编码查询字符串。
    有城市时优先 "city, country"，否则只传 country。
    """
    parts = []
    if customer.city and customer.city.strip():
        parts.append(customer.city.strip())
    if customer.country and customer.country.strip():
        parts.append(customer.country.strip())
    return ", ".join(parts) if parts else None


def _query_nominatim(query: str) -> Optional[Tuple[float, float, str]]:
    """查询 Nominatim，返回 (lat, lng, display_name) 或 None"""
    try:
        location = _geocode(query)
        if location:
            return (location.latitude, location.longitude, location.address or "")
        return None
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.error("Nominatim 查询异常: query=%s, error=%s", query, e)
        return None


def _get_country_center(country_name: Optional[str]) -> Tuple[float, float]:
    """从预置字典获取国家中心坐标，兜底 (20, 0)"""
    return _COUNTRY_CENTERS.get(country_name or "", (20.0, 0.0))


def _add_geocode_cache(db: Session, cache_key: str, country: Optional[str],
                       city: Optional[str], lat: float, lng: float,
                       display_name: str = "") -> None:
    """安全写入地理编码缓存（flush 立即生效，重复 key 自动忽略）"""
    try:
        db.add(GeocodeCache(
            query_key=cache_key,
            country=country,
            city=city,
            latitude=lat,
            longitude=lng,
            display_name=display_name,
        ))
        db.flush()
    except Exception:
        db.rollback()


def geocode_customer(db: Session, customer: Customer, auto_commit: bool = True) -> bool:
    """
    对单个客户进行地理编码。

    流程：
      - 有 city -> 精确查询 "city, country" -> 缓存结果 -> 直接定位
      - 无 city -> 查询国家中心 -> 施加随机抖动 -> 同国标记分散

    Args:
        db: 数据库会话
        customer: 客户对象
        auto_commit: 是否在修改后立即 db.commit()

    Returns:
        True 表示成功，False 表示失败或跳过
    """
    if customer.geocode_status == "done":
        return False  # 已编码，跳过

    query = _build_query(customer)
    if not query:
        customer.geocode_status = "failed"
        if auto_commit:
            db.commit()
        logger.warning("客户 %s (ID=%s) 缺少地址信息", customer.company_name, customer.id)
        return False

    # ================================================================
    # 场景 A：客户有城市数据 → 精确查询城市级坐标
    # ================================================================
    if customer.city and customer.city.strip():
        cache_key = f"city:{customer.city.strip()}|country:{customer.country or ''}"

        # 查缓存
        cached = db.query(GeocodeCache).filter(GeocodeCache.query_key == cache_key).first()
        if cached:
            customer.latitude = cached.latitude
            customer.longitude = cached.longitude
            customer.geocode_status = "done"
            cached.hits = (cached.hits or 0) + 1
            if auto_commit:
                db.commit()
            logger.info("地理编码缓存命中（城市级）: %s -> (%.4f, %.4f)",
                        query, cached.latitude, cached.longitude)
            return True

        # 查 Nominatim
        logger.info("正在地理编码（城市级）: 客户=%s, 查询=%s", customer.company_name, query)
        result = _query_nominatim(query)
        if result:
            lat, lng, display_name = result
            customer.latitude = lat
            customer.longitude = lng
            customer.geocode_status = "done"
            _add_geocode_cache(db, cache_key, customer.country, customer.city.strip(),
                               lat, lng, display_name)
            if auto_commit:
                db.commit()
            logger.info("地理编码成功（城市级）: %s -> (%.4f, %.4f)", query, lat, lng)
            return True
        else:
            customer.geocode_status = "failed"
            if auto_commit:
                db.commit()
            logger.warning("地理编码无结果（城市级）: %s, 查询=%s", customer.company_name, query)
            return False

    # ================================================================
    # 场景 B：客户没有城市数据 → 国家中心 + 抖动（每个客户独立）
    # ================================================================
    country_key = f"country_center:{customer.country or ''}"

    # 查缓存：看是否已有该国家的中心坐标
    cached_center = db.query(GeocodeCache).filter(
        GeocodeCache.query_key == country_key
    ).first()

    if cached_center:
        base_lat = cached_center.latitude
        base_lng = cached_center.longitude
    else:
        # 用 Nominatim 查国家
        result = _query_nominatim(query)  # query 此时 = 国家名
        if result:
            base_lat, base_lng, display_name = result
            _add_geocode_cache(db, country_key, customer.country, None,
                               base_lat, base_lng, display_name)
        else:
            base_lat, base_lng = _get_country_center(customer.country)

    # 施加抖动，使同国标记分散
    # 注：前端 map.js 对同样条件（无城市）也会施加 ±0.3° 抖动，
    # 两者叠加是设计意图——后端保证写入 DB 的坐标已分散，
    # 前端也保留抖动逻辑，在未重新 geocode 的数据上同样生效。
    jittered_lat = base_lat + random.uniform(-_JITTER_RANGE, _JITTER_RANGE)
    jittered_lng = base_lng + random.uniform(-_JITTER_RANGE, _JITTER_RANGE)

    customer.latitude = jittered_lat
    customer.longitude = jittered_lng
    customer.geocode_status = "done"

    if auto_commit:
        db.commit()
    logger.info("地理编码成功（国家级+抖动）: %s -> (%.4f, %.4f)",
                customer.company_name, jittered_lat, jittered_lng)
    return True


def batch_geocode(db: Session) -> Dict[str, int]:
    """
    批量地理编码：处理所有 geocode_status != "done" 的客户。
    每 50 条提交一次批量事务以提升性能。

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

    BATCH_SIZE = 50
    for i, customer in enumerate(pending):
        # 完全无地址信息直接跳过
        if not _build_query(customer):
            customer.geocode_status = "failed"
            skipped += 1
            continue

        result = geocode_customer(db, customer, auto_commit=False)
        if result:
            succeeded += 1
        else:
            if customer.geocode_status == "done":
                skipped += 1
            else:
                failed += 1

        # 每 BATCH_SIZE 条提交一次
        if (i + 1) % BATCH_SIZE == 0:
            try:
                db.commit()
                logger.debug("批量地理编码已提交 %s/%s 条", i + 1, total)
            except Exception as e:
                logger.error("批量地理编码中间提交失败: %s", e)
                db.rollback()

    # 最终提交
    try:
        db.commit()
        logger.info("批量地理编码最终提交成功")
    except Exception as e:
        logger.error("批量地理编码最终提交失败: %s", e)
        db.rollback()

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
