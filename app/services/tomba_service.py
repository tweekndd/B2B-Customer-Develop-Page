"""
Tomba 邮箱查找服务（Phase 1 新增）
封装 Tomba.io API V1，提供缓存层、配额优化、使用统计

Tomba 优势：
- 无结果不扣费
- 返回数据丰富（含领英、电话、部门、置信度评分）
- 同一域名 30 天内重复查询只计一次
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

from app.database import TombaCache, EmailQuotaLog

logger = logging.getLogger(__name__)

# ── 环境变量配置 ──
TOMBA_API_KEY = os.environ.get("TOMBA_API_KEY", "").strip()
TOMBA_API_SECRET = os.environ.get("TOMBA_API_SECRET", "").strip()

# ── 配额管理（全局计数器，进程内有效） ──
_quota_usage = {
    "domain_search": 0,
    "email_finder": 0,
    "email_verifier": 0,
    "cache_hits": 0,
    "no_result_credits_saved": 0,
    "last_reset": datetime.datetime.utcnow().isoformat(),
}

# 缓存有效期（秒），默认 7 天
TOMBA_CACHE_TTL = int(os.environ.get("TOMBA_CACHE_TTL", str(7 * 24 * 3600)))

# 请求间隔（秒）
TOMBA_REQUEST_DELAY = float(os.environ.get("TOMBA_REQUEST_DELAY", "0.3"))


class TombaError(Exception):
    """Tomba API 调用异常"""
    def __init__(self, message: str, status_code: int = 500, api_response: dict = None):
        self.status_code = status_code
        self.api_response = api_response or {}
        super().__init__(message)


class TombaClient:
    """Tomba API 客户端（带本地缓存层）"""

    BASE_URL = "https://api.tomba.io/v1"

    def __init__(self, api_key: str = None, api_secret: str = None, db: Session = None):
        self.api_key = api_key or TOMBA_API_KEY
        self.api_secret = api_secret or TOMBA_API_SECRET
        if not self.api_key or not self.api_secret:
            raise TombaError(
                "Tomba API Key/Secret 未配置。请在环境变量中设置 TOMBA_API_KEY 和 TOMBA_API_SECRET。",
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
            row = self.db.query(TombaCache).filter(
                TombaCache.cache_key == cache_key
            ).first()
            if row:
                age = (datetime.datetime.utcnow() - row.created_at).total_seconds()
                if age <= TOMBA_CACHE_TTL:
                    row.hits = (row.hits or 0) + 1
                    self.db.commit()
                    _quota_usage["cache_hits"] += 1
                    logger.debug(f"[Tomba] 缓存命中: {cache_key[:12]}... (年龄 {age:.0f}s)")
                    return json.loads(row.result)
                else:
                    self.db.delete(row)
                    self.db.commit()
                    logger.debug(f"[Tomba] 缓存过期: {cache_key[:12]}...")
            return None
        except Exception as e:
            logger.warning(f"[Tomba] 缓存读取失败: {e}")
            return None

    def _cache_set(self, cache_key: str, domain: str, query_type: str, result: dict):
        """写入本地缓存"""
        if not self.db:
            return
        try:
            row = TombaCache(
                cache_key=cache_key,
                domain=domain,
                query_type=query_type,
                result=json.dumps(result, ensure_ascii=False),
                created_at=datetime.datetime.utcnow(),
            )
            self.db.add(row)
            self.db.commit()
            logger.debug(f"[Tomba] 缓存写入: {cache_key[:12]}... ({query_type})")
        except Exception as e:
            self.db.rollback()
            logger.warning(f"[Tomba] 缓存写入失败: {e}")

    # ───────────────────────────────────────────
    # HTTP 请求
    # ───────────────────────────────────────────

    def _rate_limit(self):
        """请求间隔控制"""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < TOMBA_REQUEST_DELAY:
            time.sleep(TOMBA_REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """通用 GET 请求（带重试和错误处理）"""
        self._rate_limit()
        if params is None:
            params = {}

        headers = {
            "X-Tomba-Key": self.api_key,
            "X-Tomba-Secret": self.api_secret,
            "Accept": "application/json",
        }

        url = f"{self.BASE_URL}/{endpoint}"
        logger.debug(f"[Tomba] 请求: GET {endpoint} params={params}")

        for attempt in range(2):
            try:
                with httpx.Client(timeout=20) as client:
                    resp = client.get(url, params=params, headers=headers)
                data = resp.json()
            except httpx.TimeoutException:
                logger.warning(f"[Tomba] 请求超时: {endpoint}")
                raise TombaError(f"Tomba API 请求超时: {endpoint}", status_code=504)
            except httpx.RequestError as e:
                logger.warning(f"[Tomba] 请求失败: {e}")
                if attempt == 0:
                    time.sleep(1)
                    continue
                raise TombaError(f"Tomba API 连接失败: {e}", status_code=502)
            except (json.JSONDecodeError, ValueError):
                raise TombaError(
                    f"Tomba API 返回非 JSON 响应: {resp.status_code} {resp.text[:200]}",
                    status_code=resp.status_code,
                )

            if resp.status_code == 429:
                logger.warning("[Tomba] 触发速率限制，等待 2 秒后重试")
                time.sleep(2)
                if attempt == 0:
                    continue
                raise TombaError("Tomba API 速率限制已触发", status_code=429)

            if resp.status_code == 401:
                raise TombaError(
                    "Tomba API Key/Secret 无效，请检查配置",
                    status_code=401,
                    api_response=data,
                )

            if resp.status_code != 200:
                error_msg = data.get("message", str(data))
                raise TombaError(
                    f"Tomba API 错误 [{resp.status_code}]: {error_msg}",
                    status_code=resp.status_code,
                    api_response=data,
                )

            return data

        raise TombaError("Tomba API 请求异常", status_code=500)

    # ───────────────────────────────────────────
    # API 方法（自动缓存 + 配额记录）
    # ───────────────────────────────────────────

    def domain_search(
        self,
        domain: str,
        company: str = None,
        page: int = 1,
        limit: int = 10,
        country: str = None,
        department: str = None,
        enrich_mobile: bool = False,
        force_refresh: bool = False,
    ) -> dict:
        """
        域名全量搜索（消耗搜索额度）
        结果按 domain+page+参数 缓存 7 天
        无结果不扣费（Tomba 官方规则）

        Args:
            domain: 公司域名（必填）
            company: 公司名（可选，domain 优先）
            page: 页码，默认 1
            limit: 每页数量，可选 10/20/50
            country: 国家筛选（两位字母代码）
            department: 部门筛选
            enrich_mobile: 是否获取电话号码
            force_refresh: 强制刷新（跳过缓存）
        """
        endpoint = "domain-search"
        params = {"domain": domain, "page": page, "limit": limit}
        if company:
            params["company"] = company
        if country:
            params["country"] = country
        if department:
            params["department"] = department
        if enrich_mobile:
            params["enrich_mobile"] = "true"

        cache_key = self._build_cache_key(endpoint, params)
        if not force_refresh:
            cached = self._cache_get(cache_key)
            if cached:
                _quota_usage["domain_search"] += 1
                return cached

        try:
            data = self._get(endpoint, params)
            _quota_usage["domain_search"] += 1

            # 检查是否有结果：Tomba 无结果不扣费
            emails = data.get("data", {}).get("emails", [])
            if not emails:
                _quota_usage["no_result_credits_saved"] += 1
                logger.info(f"[Tomba] {domain} 无结果（本次不扣费）")

            self._cache_set(cache_key, domain, "domain_search", data)
            self._log_quota(domain, "domain_search", len(emails), 1 if emails else 0)
            return data

        except TombaError as e:
            # 404 或其它错误时记录但不扣费
            if e.status_code in (404, 400):
                logger.info(f"[Tomba] {domain} 未找到数据: {e}")
                self._log_quota(domain, "domain_search", 0, 0, success=0, error=str(e)[:200])
                return {"data": {"organization": {}, "emails": []}, "meta": {"total": 0}}
            raise

    def email_finder(
        self,
        domain: str = None,
        company: str = None,
        first_name: str = None,
        last_name: str = None,
        linkedin_handle: str = None,
        force_refresh: bool = False,
    ) -> dict:
        """
        按姓名精确查找邮箱（消耗搜索额度，找不到不扣费）

        Args:
            domain: 公司域名（与 company 二选一）
            company: 公司名
            first_name: 名
            last_name: 姓
            linkedin_handle: 领英 handle
            force_refresh: 强制刷新
        """
        endpoint = "email-finder"
        params = {}
        if domain:
            params["domain"] = domain
        if company:
            params["company"] = company
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name
        if linkedin_handle:
            params["linkedin_handle"] = linkedin_handle

        if not params:
            raise TombaError("Email Finder 需要提供 domain / company / linkedin_handle 之一", status_code=400)

        cache_key = self._build_cache_key(endpoint, params)
        if not force_refresh:
            cached = self._cache_get(cache_key)
            if cached:
                _quota_usage["email_finder"] += 1
                return cached

        try:
            data = self._get(endpoint, params)
            _quota_usage["email_finder"] += 1

            has_result = bool(data.get("data", {}).get("email"))
            if not has_result:
                _quota_usage["no_result_credits_saved"] += 1

            cache_domain = domain or company or "unknown"
            self._cache_set(cache_key, cache_domain, "email_finder", data)
            self._log_quota(cache_domain, "email_finder", 1 if has_result else 0, 1 if has_result else 0)
            return data

        except TombaError as e:
            if e.status_code in (404, 400):
                logger.info(f"[Tomba] Email Finder 未找到: {e}")
                self._log_quota(domain or company or "unknown", "email_finder", 0, 0, success=0, error=str(e)[:200])
                return {"data": {}}
            raise

    # ───────────────────────────────────────────
    # 配额记录（持久化）
    # ───────────────────────────────────────────

    def _log_quota(self, domain: str, query_type: str, result_count: int,
                   credits_consumed: int, success: int = 1, error: str = ""):
        """记录配额使用到数据库"""
        if not self.db:
            return
        try:
            log = EmailQuotaLog(
                source="tomba",
                query_type=query_type,
                domain=domain,
                result_count=result_count,
                credits_consumed=credits_consumed,
                success=success,
                error_message=error or None,
                created_at=datetime.datetime.utcnow(),
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.warning(f"[Tomba] 配额记录写入失败: {e}")

    # ───────────────────────────────────────────
    # 配额统计
    # ───────────────────────────────────────────

    def get_usage_stats(self) -> dict:
        """获取当前会话的配额使用统计"""
        return {
            **_quota_usage,
            "total_api_calls": (
                _quota_usage["domain_search"]
                + _quota_usage["email_finder"]
                + _quota_usage["email_verifier"]
                - _quota_usage["cache_hits"]
            ),
            "total_searches": _quota_usage["domain_search"] + _quota_usage["email_finder"],
        }

    def get_cache_stats(self) -> dict:
        """获取缓存统计"""
        if not self.db:
            return {"enabled": False}
        try:
            total = self.db.query(TombaCache).count()
            by_type = {}
            for row in self.db.query(TombaCache.query_type, TombaCache.hits).all():
                t = row[0]
                by_type[t] = by_type.get(t, 0) + 1
            return {
                "enabled": True,
                "total_entries": total,
                "by_type": by_type,
            }
        except Exception as e:
            return {"enabled": True, "error": str(e)}

    def get_quota_history(self, limit: int = 50) -> list:
        """获取最近的配额使用记录"""
        if not self.db:
            return []
        try:
            logs = self.db.query(EmailQuotaLog).filter(
                EmailQuotaLog.source == "tomba"
            ).order_by(EmailQuotaLog.created_at.desc()).limit(limit).all()
            return [
                {
                    "id": log.id,
                    "query_type": log.query_type,
                    "domain": log.domain,
                    "result_count": log.result_count,
                    "credits_consumed": log.credits_consumed,
                    "success": log.success,
                    "error_message": log.error_message,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ]
        except Exception as e:
            logger.warning(f"[Tomba] 配额历史查询失败: {e}")
            return []


# ── 便捷函数 ──

def get_tomba_client(db: Session = None) -> TombaClient:
    """获取 Tomba 客户端实例"""
    return TombaClient(db=db)


def clear_tomba_cache(db: Session = None) -> int:
    """清除所有 Tomba 缓存"""
    if not db:
        return 0
    try:
        count = db.query(TombaCache).delete()
        db.commit()
        logger.info(f"[Tomba] 已清除 {count} 条缓存")
        return count
    except Exception as e:
        db.rollback()
        logger.error(f"[Tomba] 清除缓存失败: {e}")
        return 0
