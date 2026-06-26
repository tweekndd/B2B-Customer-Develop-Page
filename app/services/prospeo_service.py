"""
Prospeo 邮箱发现服务（V3.2.2 新增）
封装 Prospeo.io Search Person + Enrich Person API，提供缓存层、配额管理

Prospeo 特点：
- Search Person：按 20+ 维度搜索联系人（不含邮箱），1 积分/页（25 条）
- Enrich Person：根据 person_id 补全邮箱+手机号，1 积分/邮箱
- 90 天内同一人重复 Enrich 免费
- 无结果不扣费

本服务集成到瀑布流中作为第3级：
  Hunter → Tomba → Prospeo (Search+Enrich) → 自研抓取兜底
"""
import os
import json
import hashlib
import datetime
import time
import logging
from typing import Optional, List, Dict

import httpx
from sqlalchemy.orm import Session

from app.database import ProspeoCache

logger = logging.getLogger(__name__)

# ── 环境变量配置 ──
PROSPEO_API_KEY = os.environ.get("PROSPEO_API_KEY", "").strip()

# ── 配额管理（全局计数器，进程内有效） ──
_quota_usage = {
    "search_person": 0,
    "enrich_person": 0,
    "cache_hits": 0,
    "no_result_credits_saved": 0,
    "last_reset": datetime.datetime.utcnow().isoformat(),
}

# 缓存有效期（秒），默认 7 天
PROSPEO_CACHE_TTL = int(os.environ.get("PROSPEO_CACHE_TTL", str(7 * 24 * 3600)))

# 请求间隔（秒）
PROSPEO_REQUEST_DELAY = float(os.environ.get("PROSPEO_REQUEST_DELAY", "0.5"))


class ProspeoError(Exception):
    """Prospeo API 调用异常"""
    def __init__(self, message: str, status_code: int = 500, api_response: dict = None):
        self.status_code = status_code
        self.api_response = api_response or {}
        super().__init__(message)


class ProspeoClient:
    """Prospeo API 客户端（Search + Enrich，带本地缓存层）"""

    SEARCH_URL = "https://api.prospeo.io/search-person"
    ENRICH_URL = "https://api.prospeo.io/enrich-person"

    def __init__(self, api_key: str = None, db: Session = None):
        self.api_key = api_key or PROSPEO_API_KEY
        if not self.api_key:
            raise ProspeoError(
                "Prospeo API Key 未配置。请在环境变量中设置 PROSPEO_API_KEY。",
                status_code=401,
            )
        self.db = db
        self._last_request_time = 0.0

    # ───────────────────────────────────────────
    # 缓存构建
    # ───────────────────────────────────────────

    def _build_cache_key(self, query_type: str, params: dict) -> str:
        """生成缓存键：对参数排序后 MD5"""
        raw = query_type + "|" + json.dumps(params, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(raw.encode()).hexdigest()

    def _cache_get(self, cache_key: str) -> Optional[dict]:
        """从本地缓存读结果（检查 TTL）"""
        if not self.db:
            return None
        try:
            row = self.db.query(ProspeoCache).filter(
                ProspeoCache.cache_key == cache_key
            ).first()
            if row:
                age = (datetime.datetime.utcnow() - row.created_at).total_seconds()
                if age <= PROSPEO_CACHE_TTL:
                    row.hits = (row.hits or 0) + 1
                    self.db.commit()
                    _quota_usage["cache_hits"] += 1
                    logger.debug(f"[Prospeo] 缓存命中: {cache_key[:12]}... (年龄 {age:.0f}s)")
                    return json.loads(row.result)
                else:
                    self.db.delete(row)
                    self.db.commit()
                    logger.debug(f"[Prospeo] 缓存过期: {cache_key[:12]}...")
            return None
        except Exception as e:
            logger.warning(f"[Prospeo] 缓存读取失败: {e}")
            return None

    def _cache_set(self, cache_key: str, domain: str, query_type: str,
                   result: dict, person_id: str = None):
        """写入本地缓存"""
        if not self.db:
            return
        try:
            row = ProspeoCache(
                cache_key=cache_key,
                domain=domain,
                query_type=query_type,
                person_id=person_id,
                result=json.dumps(result, ensure_ascii=False),
                created_at=datetime.datetime.utcnow(),
            )
            self.db.add(row)
            self.db.commit()
            logger.debug(f"[Prospeo] 缓存写入: {cache_key[:12]}... ({query_type})")
        except Exception as e:
            self.db.rollback()
            logger.warning(f"[Prospeo] 缓存写入失败: {e}")

    # ───────────────────────────────────────────
    # HTTP 请求
    # ───────────────────────────────────────────

    def _rate_limit(self):
        """请求间隔控制"""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < PROSPEO_REQUEST_DELAY:
            time.sleep(PROSPEO_REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def _post(self, url: str, body: dict) -> dict:
        """通用 POST 请求（带重试和错误处理）"""
        self._rate_limit()

        headers = {
            "X-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        logger.debug(f"[Prospeo] 请求: POST {url} body={body}")

        for attempt in range(2):  # 最多重试 1 次
            try:
                with httpx.Client(timeout=20) as client:
                    resp = client.post(url, json=body, headers=headers)
                data = resp.json()
            except httpx.TimeoutException:
                logger.warning(f"[Prospeo] 请求超时: {url}")
                raise ProspeoError("Prospeo API 请求超时", status_code=504)
            except httpx.RequestError as e:
                logger.warning(f"[Prospeo] 请求失败: {e}")
                if attempt == 0:
                    time.sleep(1)
                    continue
                raise ProspeoError(f"Prospeo API 连接失败: {e}", status_code=502)
            except (json.JSONDecodeError, ValueError):
                raise ProspeoError(
                    f"Prospeo API 返回非 JSON 响应: {resp.status_code} {resp.text[:200]}",
                    status_code=resp.status_code,
                )

            if resp.status_code == 429:
                logger.warning("[Prospeo] 触发速率限制，等待 3 秒后重试")
                time.sleep(3)
                if attempt == 0:
                    continue
                raise ProspeoError("Prospeo API 速率限制已触发，请降低请求频率", status_code=429)

            if resp.status_code == 401:
                raise ProspeoError(
                    "Prospeo API Key 无效，请检查 PROSPEO_API_KEY 配置",
                    status_code=401,
                    api_response=data,
                )

            if resp.status_code != 200:
                error_code = data.get("error_code", "UNKNOWN")
                error_msg = data.get("filter_error", str(data))
                raise ProspeoError(
                    f"Prospeo API 错误 [{resp.status_code}]: {error_code} - {error_msg}",
                    status_code=resp.status_code,
                    api_response=data,
                )

            # 检查业务错误
            if data.get("error") is True:
                error_code = data.get("error_code", "UNKNOWN")
                # NO_MATCH / NO_RESULTS 不算异常，只是没找到数据
                if error_code in ("NO_MATCH", "NO_RESULTS"):
                    logger.info(f"[Prospeo] 未找到匹配数据: {error_code}")
                    return data
                raise ProspeoError(
                    f"Prospeo API 业务错误: {error_code}",
                    status_code=400,
                    api_response=data,
                )

            return data

        raise ProspeoError("Prospeo API 请求异常", status_code=500)

    # ───────────────────────────────────────────
    # API 方法
    # ───────────────────────────────────────────

    def search_people(self, domain: str, force_refresh: bool = False) -> dict:
        """
        Search Person — 按域名搜索联系人（消耗搜索额度）

        Args:
            domain: 公司域名，如 "intercom.com"
            force_refresh: 强制刷新（跳过缓存）

        Returns:
            {
                "error": false,
                "free": false,
                "results": [{"person": {...}, "company": {...}}, ...],
                "pagination": {"current_page": 1, "total_count": N, ...}
            }
            或无结果时 {"error": false, "results": [], "pagination": {...}}
        """
        body = {
            "page": 1,
            "filters": {
                "company": {
                    "websites": {
                        "include": [domain],
                    }
                }
            },
        }

        cache_key = self._build_cache_key("search_person", body)
        if not force_refresh:
            cached = self._cache_get(cache_key)
            if cached:
                _quota_usage["search_person"] += 1
                return cached

        try:
            data = self._post(self.SEARCH_URL, body)

            # 检查是否有结果
            results = data.get("results", [])
            if not results:
                _quota_usage["no_result_credits_saved"] += 1
                logger.info(f"[Prospeo] {domain} Search 无结果（本次不扣费）")
            else:
                _quota_usage["search_person"] += 1

            self._cache_set(cache_key, domain, "search_person", data)
            return data

        except ProspeoError as e:
            if e.status_code in (400, 404):
                logger.info(f"[Prospeo] {domain} Search 未找到数据: {e}")
                _quota_usage["no_result_credits_saved"] += 1
                return {"error": False, "results": [], "pagination": {"total_count": 0}}
            raise

    def enrich_person(self, person_id: str, domain: str,
                      force_refresh: bool = False) -> dict:
        """
        Enrich Person — 按 person_id 补全个人资料+邮箱（消耗补全额度）

        Args:
            person_id: Search 返回的 person_id
            domain: 公司域名（用于缓存键）
            force_refresh: 强制刷新（跳过缓存）

        Returns:
            {
                "error": false,
                "free_enrichment": false,
                "person": {...},  # 含 email/mobile 字段
                "company": {...} or null,
            }
        """
        body = {
            "data": {
                "person_id": person_id,
            },
        }

        cache_key = self._build_cache_key("enrich_person", {"person_id": person_id})
        if not force_refresh:
            cached = self._cache_get(cache_key)
            if cached:
                _quota_usage["enrich_person"] += 1
                return cached

        try:
            data = self._post(self.ENRICH_URL, body)

            # 检查是否有有效结果（person 不为空且邮箱被揭示）
            person = data.get("person")
            has_result = person is not None

            if has_result:
                _quota_usage["enrich_person"] += 1
            else:
                _quota_usage["no_result_credits_saved"] += 1
                logger.debug(f"[Prospeo] Enrich {person_id[:12]}... 无结果")

            self._cache_set(cache_key, domain, "enrich_person", data, person_id=person_id)
            return data

        except ProspeoError as e:
            if e.status_code in (400, 404):
                logger.debug(f"[Prospeo] Enrich {person_id[:12]}... 失败: {e}")
                _quota_usage["no_result_credits_saved"] += 1
                return {"error": True, "error_code": "NO_MATCH", "person": None}
            raise

    # ───────────────────────────────────────────
    # 便捷方法：Search → Enrich 一步完成
    # ───────────────────────────────────────────

    def search_and_enrich(self, domain: str, limit: int = 25) -> List[Dict]:
        """
        搜索域名下联系人并补全邮箱（Search → Enrich 组合调用）

        流程：
        1. Search Person（只取第一页，最多 25 人）
        2. 对搜索结果中的人逐个 Enrich，获取邮箱+手机号
        3. 只返回邮箱被揭示（revealed=true）的结果

        Args:
            domain: 公司域名
            limit: 最多补全人数（默认 25 = 一页）

        Returns:
            [{
                "email": "...",
                "first_name": "...",
                "last_name": "...",
                "full_name": "...",
                "position": "...",
                "linkedin": "...",
                "phone": "...",
                "verification": "VERIFIED" | "ACCEPT_ALL" | ...,
                "person_id": "...",
            }, ...]
        """
        # Step 1: Search
        search_data = self.search_people(domain)
        results = search_data.get("results", [])
        if not results:
            logger.info(f"[Prospeo] {domain} Search 无联系人")
            return []

        total_available = search_data.get("pagination", {}).get("total_count", 0)
        logger.info(f"[Prospeo] {domain} Search 找到 {len(results)} 人（共 {total_available}）")

        # Step 2: Enrich 每个人
        enriched_list = []
        for item in results[:limit]:
            person = item.get("person") or {}
            pid = person.get("person_id")
            if not pid:
                continue

            try:
                enrich_data = self.enrich_person(pid, domain)
                if enrich_data.get("error"):
                    continue

                eperson = enrich_data.get("person") or {}

                # 只取邮箱被揭示的
                email_info = eperson.get("email") or {}
                if not email_info.get("revealed"):
                    continue

                email = email_info.get("email", "")
                if not email or "@" not in email:
                    continue

                # 手机信息
                mobile_info = eperson.get("mobile") or {}

                enriched_list.append({
                    "email": email,
                    "first_name": eperson.get("first_name", ""),
                    "last_name": eperson.get("last_name", ""),
                    "full_name": eperson.get("full_name", ""),
                    "position": eperson.get("current_job_title", ""),
                    "linkedin": eperson.get("linkedin_url", ""),
                    "phone": mobile_info.get("mobile", ""),
                    "verification": email_info.get("status", ""),
                    "person_id": pid,
                })

            except ProspeoError as e:
                logger.warning(f"[Prospeo] Enrich {pid[:12]}... 失败: {e}")
                continue

        logger.info(f"[Prospeo] {domain} 最终获取 {len(enriched_list)} 个邮箱")
        return enriched_list

    # ───────────────────────────────────────────
    # 配额统计
    # ───────────────────────────────────────────

    def get_usage_stats(self) -> dict:
        """获取当前会话的配额使用统计"""
        return {
            **_quota_usage,
            "total_api_calls": (
                _quota_usage["search_person"]
                + _quota_usage["enrich_person"]
                - _quota_usage["cache_hits"]
            ),
            "total_searches": _quota_usage["search_person"],
            "total_enriches": _quota_usage["enrich_person"],
        }

    def get_cache_stats(self) -> dict:
        """获取缓存统计"""
        if not self.db:
            return {"enabled": False}
        try:
            total = self.db.query(ProspeoCache).count()
            by_type = {}
            for row in self.db.query(ProspeoCache.query_type, ProspeoCache.hits).all():
                t = row[0]
                by_type[t] = by_type.get(t, 0) + 1
            return {
                "enabled": True,
                "total_entries": total,
                "by_type": by_type,
            }
        except Exception as e:
            return {"enabled": True, "error": str(e)}


# ── 便捷函数 ──

def get_prospeo_client(db: Session = None) -> ProspeoClient:
    """获取 Prospeo 客户端实例"""
    return ProspeoClient(db=db)


def clear_prospeo_cache(db: Session = None) -> int:
    """清除所有 Prospeo 缓存"""
    if not db:
        return 0
    try:
        count = db.query(ProspeoCache).delete()
        db.commit()
        logger.info(f"[Prospeo] 已清除 {count} 条缓存")
        return count
    except Exception as e:
        db.rollback()
        logger.error(f"[Prospeo] 清除缓存失败: {e}")
        return 0
