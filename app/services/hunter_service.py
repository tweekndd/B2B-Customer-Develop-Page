"""
Hunter 邮箱查找服务（V3.0）
封装 Hunter.io API V2，提供缓存层、配额优化、使用统计

核心优化策略：
1. 所有查询结果写入本地 SQLite 缓存（7 天有效），API 调用前先查缓存
2. Email Count（免费）始终优先调用，评估数据价值后再决定是否消耗搜索额度
3. Domain Search 结果自带 verification，不再额外调用 Email Verifier
4. 仅当 Domain Search 找不到目标人员时才降级到 Email Finder
5. 自动记录配额使用，帮助用户控制月度消耗
"""
import os
import json
import hashlib
import datetime
import time
import logging
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.database import HunterCache

logger = logging.getLogger(__name__)

# ── 环境变量配置 ──
HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY", "").strip()

# ── 配额管理（全局计数器，进程内有效） ──
_quota_usage = {
    "email_count": 0,
    "domain_search": 0,
    "email_finder": 0,
    "email_verifier": 0,
    "cache_hits": 0,
    "last_reset": datetime.datetime.utcnow().isoformat(),
}

# 缓存有效期（秒），默认 7 天
HUNTER_CACHE_TTL = int(os.environ.get("HUNTER_CACHE_TTL", str(7 * 24 * 3600)))

# 请求间隔（秒），避免触发 Hunter 速率限制
HUNTER_REQUEST_DELAY = float(os.environ.get("HUNTER_REQUEST_DELAY", "0.3"))


class HunterError(Exception):
    """Hunter API 调用异常"""
    def __init__(self, message: str, status_code: int = 500, api_response: dict = None):
        self.status_code = status_code
        self.api_response = api_response or {}
        super().__init__(message)


class HunterClient:
    """Hunter API 客户端（带本地缓存层）"""

    BASE_URL = "https://api.hunter.io/v2"

    def __init__(self, api_key: str = None, db: Session = None):
        self.api_key = api_key or HUNTER_API_KEY
        if not self.api_key:
            raise HunterError(
                "Hunter API Key 未配置。请在环境变量中设置 HUNTER_API_KEY，"
                "或使用 test-api-key 进行测试。",
                status_code=401,
            )
        self.db = db
        self._last_request_time = 0.0

    # ───────────────────────────────────────────
    # 缓存构建
    # ───────────────────────────────────────────

    def _build_cache_key(self, endpoint: str, params: dict) -> str:
        """生成缓存键：对参数排序后 MD5"""
        raw = endpoint + "|" + json.dumps(params, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(raw.encode()).hexdigest()

    def _cache_get(self, cache_key: str) -> Optional[dict]:
        """从本地缓存读结果（检查 TTL）"""
        if not self.db:
            return None
        try:
            row = self.db.query(HunterCache).filter(
                HunterCache.cache_key == cache_key
            ).first()
            if row:
                age = (datetime.datetime.utcnow() - row.created_at).total_seconds()
                if age <= HUNTER_CACHE_TTL:
                    # 更新命中次数
                    row.hits = (row.hits or 0) + 1
                    self.db.commit()
                    _quota_usage["cache_hits"] += 1
                    logger.debug(f"[Hunter] 缓存命中: {cache_key[:12]}... (年龄 {age:.0f}s)")
                    return json.loads(row.result)
                else:
                    # 缓存过期，删除
                    self.db.delete(row)
                    self.db.commit()
                    logger.debug(f"[Hunter] 缓存过期: {cache_key[:12]}...")
            return None
        except Exception as e:
            logger.warning(f"[Hunter] 缓存读取失败: {e}")
            return None

    def _cache_set(self, cache_key: str, domain: str, query_type: str, result: dict):
        """写入本地缓存"""
        if not self.db:
            return
        try:
            row = HunterCache(
                cache_key=cache_key,
                domain=domain,
                query_type=query_type,
                result=json.dumps(result, ensure_ascii=False),
                created_at=datetime.datetime.utcnow(),
            )
            self.db.add(row)
            self.db.commit()
            logger.debug(f"[Hunter] 缓存写入: {cache_key[:12]}... ({query_type})")
        except Exception as e:
            self.db.rollback()
            logger.warning(f"[Hunter] 缓存写入失败: {e}")

    # ───────────────────────────────────────────
    # HTTP 请求（含延迟和限流处理）
    # ───────────────────────────────────────────

    def _rate_limit(self):
        """请求间隔控制"""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < HUNTER_REQUEST_DELAY:
            time.sleep(HUNTER_REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """通用 GET 请求（带重试和错误处理）"""
        self._rate_limit()
        if params is None:
            params = {}
        params["api_key"] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}"
        logger.debug(f"[Hunter] 请求: GET {endpoint} params={params}")

        for attempt in range(2):  # 最多重试 1 次
            try:
                with httpx.Client(timeout=15) as client:
                    resp = client.get(url, params=params)
                data = resp.json()
            except httpx.TimeoutException:
                logger.warning(f"[Hunter] 请求超时: {endpoint}")
                raise HunterError(f"Hunter API 请求超时: {endpoint}", status_code=504)
            except httpx.RequestError as e:
                logger.warning(f"[Hunter] 请求失败: {e}")
                if attempt == 0:
                    time.sleep(1)
                    continue
                raise HunterError(f"Hunter API 连接失败: {e}", status_code=502)
            except (json.JSONDecodeError, ValueError):
                raise HunterError(
                    f"Hunter API 返回非 JSON 响应: {resp.status_code} {resp.text[:200]}",
                    status_code=resp.status_code,
                )

            if resp.status_code == 429:
                logger.warning("[Hunter] 触发速率限制，等待 2 秒后重试")
                time.sleep(2)
                if attempt == 0:
                    continue
                raise HunterError("Hunter API 速率限制已触发，请降低请求频率", status_code=429)

            if resp.status_code == 401:
                raise HunterError(
                    "Hunter API Key 无效，请检查 HUNTER_API_KEY 配置",
                    status_code=401,
                    api_response=data,
                )

            if resp.status_code == 404:
                # Hunter 找不到数据时返回 404
                logger.info(f"[Hunter] 未找到数据: {endpoint}")
                return data

            if resp.status_code != 200:
                error_msg = data.get("errors", [{}])[0].get("details", str(data))
                raise HunterError(
                    f"Hunter API 错误 [{resp.status_code}]: {error_msg}",
                    status_code=resp.status_code,
                    api_response=data,
                )

            return data

        # 不应到达这里
        raise HunterError("Hunter API 请求异常", status_code=500)

    # ───────────────────────────────────────────
    # API 方法（自动缓存）
    # ───────────────────────────────────────────

    def email_count(self, domain: str, force_refresh: bool = False) -> dict:
        """
        查询域名下的邮箱数量（免费，不消耗搜索额度）
        结果按 domain 缓存 7 天
        """
        endpoint = "email-count"
        params = {"domain": domain}
        cache_key = self._build_cache_key(endpoint, params)

        if not force_refresh:
            cached = self._cache_get(cache_key)
            if cached:
                _quota_usage["email_count"] += 1  # 缓存命中也算"已查询"
                return cached

        data = self._get(endpoint, params)
        _quota_usage["email_count"] += 1
        self._cache_set(cache_key, domain, "email_count", data)
        return data

    def domain_search(
        self,
        domain: str,
        department: str = None,
        seniority: str = None,
        limit: int = 10,
        offset: int = 0,
        force_refresh: bool = False,
    ) -> dict:
        """
        按域名全量搜索（消耗搜索额度）
        结果按 domain+department+seniority 缓存 7 天

        Free 计划限制：limit + offset ≤ 10，最多返回 10 条
        """
        endpoint = "domain-search"
        params = {"domain": domain, "limit": limit, "offset": offset}
        if department:
            params["department"] = department
        if seniority:
            params["seniority"] = seniority

        cache_key = self._build_cache_key(endpoint, params)
        if not force_refresh:
            cached = self._cache_get(cache_key)
            if cached:
                _quota_usage["domain_search"] += 1
                return cached

        data = self._get(endpoint, params)
        _quota_usage["domain_search"] += 1
        self._cache_set(cache_key, domain, "domain_search", data)
        return data

    def email_finder(
        self,
        domain: str = None,
        company: str = None,
        first_name: str = None,
        last_name: str = None,
        full_name: str = None,
        linkedin_handle: str = None,
        force_refresh: bool = False,
    ) -> dict:
        """
        按姓名精确查找邮箱（消耗搜索额度，找不到不扣费）
        结果按参数组合缓存 7 天

        最佳实践：
        - 先调 domain_search 看是否有该人，找不到再降级到此方法
        - 提供 first_name + last_name 比 full_name 效果更好
        """
        endpoint = "email-finder"
        params = {}
        if domain:
            params["domain"] = domain
        if company:
            params["company"] = company
        if first_name and last_name:
            params["first_name"] = first_name
            params["last_name"] = last_name
        elif full_name:
            params["full_name"] = full_name
        if linkedin_handle:
            params["linkedin_handle"] = linkedin_handle

        if not params:
            raise HunterError("Email Finder 需要提供 domain / company / linkedin_handle 之一", status_code=400)

        cache_key = self._build_cache_key(endpoint, params)
        if not force_refresh:
            cached = self._cache_get(cache_key)
            if cached:
                _quota_usage["email_finder"] += 1
                return cached

        data = self._get(endpoint, params)
        _quota_usage["email_finder"] += 1
        # 使用 domain 或 company 作为缓存域名
        cache_domain = domain or company or linkedin_handle or "unknown"
        self._cache_set(cache_key, cache_domain, "email_finder", data)
        return data

    def email_verifier(self, email: str, force_refresh: bool = False) -> dict:
        """
        验证单个邮箱（消耗验证额度）
        结果按 email 缓存 7 天

        优化策略：仅在需要二次确认时调用，Domain Search 结果自带验证信息
        """
        endpoint = "email-verifier"
        params = {"email": email}
        cache_key = self._build_cache_key(endpoint, params)

        if not force_refresh:
            cached = self._cache_get(cache_key)
            if cached:
                _quota_usage["email_verifier"] += 1
                return cached

        data = self._get(endpoint, params)
        _quota_usage["email_verifier"] += 1
        self._cache_set(cache_key, email.split("@")[-1], "email_verifier", data)
        return data

    # ───────────────────────────────────────────
    # 智能查找（整合缓存+额度优化策略）
    # ───────────────────────────────────────────

    def smart_find_emails(
        self,
        domain: str,
        first_name: str = None,
        last_name: str = None,
    ) -> dict:
        """
        智能邮箱查找（优先使用缓存和 Domain Search，减少额度消耗）

        策略：
        1. 先查 Email Count（免费）→ 如果 total=0 直接返回空
        2. 有姓名 → 先从缓存的 Domain Search 结果中查找
        3. 缓存找不到且需要精确查找 → 降级到 Email Finder
        4. 无姓名 → 直接 Domain Search 全量搜索

        Args:
            domain: 公司域名（必填）
            first_name: 名（可选）
            last_name: 姓（可选）

        Returns:
            {
                "source": "cache" | "domain_search" | "email_finder",
                "emails": [...],
                "quota_used": {...},
                "total_available": int,  # 该域名下可用邮箱总数
            }
        """
        quota_used = {"email_count": 0, "domain_search": 0, "email_finder": 0}
        result = {"source": None, "emails": [], "quota_used": quota_used, "total_available": 0}

        # Step 1: Email Count（免费，评估数据量）
        try:
            count_data = self.email_count(domain)
            quota_used["email_count"] += 1
        except HunterError as e:
            logger.warning(f"[Hunter] Email Count 失败: {e}")
            count_data = {"data": {"total": 0}}

        total = count_data.get("data", {}).get("total", 0)
        result["total_available"] = total

        if total == 0:
            logger.info(f"[Hunter] {domain} 在 Hunter 数据库中无邮箱数据")
            return result

        # Step 2: 有姓名 → 先尝试 Domain Search 看能否找到
        if first_name or last_name:
            try:
                search_data = self.domain_search(domain, limit=10)
                quota_used["domain_search"] += 1
                emails = search_data.get("data", {}).get("emails", [])
                # 在结果中按姓名匹配
                matched = []
                for e in emails:
                    fn_match = not first_name or (e.get("first_name") or "").lower() == first_name.lower()
                    ln_match = not last_name or (e.get("last_name") or "").lower() == last_name.lower()
                    if fn_match and ln_match:
                        matched.append(e)

                if matched:
                    result["source"] = "domain_search"
                    result["emails"] = matched
                    return result

                # Domain Search 没找到 → 降级到 Email Finder
                logger.info(f"[Hunter] Domain Search 无匹配，降级到 Email Finder: {first_name} {last_name} @ {domain}")
            except HunterError as e:
                logger.warning(f"[Hunter] Domain Search 失败，尝试 Email Finder: {e}")

            # Step 3: Email Finder 精确查找
            try:
                finder_data = self.email_finder(
                    domain=domain,
                    first_name=first_name,
                    last_name=last_name,
                )
                quota_used["email_finder"] += 1
                email_data = finder_data.get("data", {})
                if email_data.get("email"):
                    result["source"] = "email_finder"
                    result["emails"] = [{
                        "value": email_data["email"],
                        "first_name": email_data.get("first_name", first_name or ""),
                        "last_name": email_data.get("last_name", last_name or ""),
                        "position": email_data.get("position", ""),
                        "confidence": email_data.get("confidence", 0),
                        "verification": email_data.get("verification", {}),
                    }]
                return result
            except HunterError as e:
                logger.warning(f"[Hunter] Email Finder 失败: {e}")
                return result

        # 无姓名 → 全量 Domain Search
        try:
            search_data = self.domain_search(domain, limit=10)
            quota_used["domain_search"] += 1
            emails = search_data.get("data", {}).get("emails", [])
            result["source"] = "domain_search"
            result["emails"] = emails
        except HunterError as e:
            logger.warning(f"[Hunter] Domain Search 失败: {e}")

        return result

    # ───────────────────────────────────────────
    # 配额统计
    # ───────────────────────────────────────────

    def get_usage_stats(self) -> dict:
        """获取当前会话的配额使用统计"""
        return {
            ** _quota_usage,
            "cache_hits": _quota_usage["cache_hits"],
            "total_api_calls": (
                _quota_usage["email_count"]
                + _quota_usage["domain_search"]
                + _quota_usage["email_finder"]
                + _quota_usage["email_verifier"]
                - _quota_usage["cache_hits"]
            ),
            "total_searches": _quota_usage["domain_search"] + _quota_usage["email_finder"],
            "total_verifications": _quota_usage["email_verifier"],
        }

    def get_cache_stats(self) -> dict:
        """获取缓存统计"""
        if not self.db:
            return {"enabled": False}
        try:
            total = self.db.query(HunterCache).count()
            by_type = {}
            for row in self.db.query(HunterCache.query_type, HunterCache.hits).all():
                t = row[0]
                by_type[t] = by_type.get(t, 0) + 1
            return {
                "enabled": True,
                "total_entries": total,
                "by_type": by_type,
            }
        except Exception as e:
            return {"enabled": True, "error": str(e)}


# ── 便捷函数（快速调用） ──

def get_hunter_client(db: Session = None) -> HunterClient:
    """获取 Hunter 客户端实例"""
    return HunterClient(db=db)


def clear_hunter_cache(db: Session = None) -> int:
    """清除所有 Hunter 缓存"""
    if not db:
        return 0
    try:
        count = db.query(HunterCache).delete()
        db.commit()
        logger.info(f"[Hunter] 已清除 {count} 条缓存")
        return count
    except Exception as e:
        db.rollback()
        logger.error(f"[Hunter] 清除缓存失败: {e}")
        return 0
