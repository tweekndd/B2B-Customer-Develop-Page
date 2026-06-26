"""
缓存管理服务（V2.0 新增）
统一管理 search_cache, website_cache, analysis_cache 的读写
避免重复搜索、重复抓取、重复AI分析
"""
import json
import hashlib
import datetime
import os
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.database import SearchCache, WebsiteCache, AnalysisCache


# ──── 搜索缓存（30天有效） ────

SEARCH_CACHE_EXPIRE_DAYS = 30


def get_search_cache(db: Session, keyword: str, country: str) -> List[Dict]:
    """
    获取搜索缓存
    相同关键词+国家，30天内有效
    返回缓存的搜索结果列表，如果过期或不存在返回空列表
    """
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=SEARCH_CACHE_EXPIRE_DAYS)
    cached = db.query(SearchCache).filter(
        SearchCache.keyword == keyword,
        SearchCache.country == country,
        SearchCache.created_at >= cutoff,
    ).all()

    if not cached:
        return []

    results = []
    for c in cached:
        results.append({
            "website": c.website,
            "title": c.title or "",
            "snippet": c.snippet or "",
        })

    return results


def save_search_cache(db: Session, keyword: str, country: str, results: List[Dict]):
    """保存搜索结果到缓存"""
    now = datetime.datetime.utcnow()
    for r in results:
        cache_entry = SearchCache(
            keyword=keyword,
            country=country,
            website=r.get("website", ""),
            title=r.get("title", ""),
            snippet=r.get("snippet", ""),
            created_at=now,
        )
        db.add(cache_entry)
    db.commit()


def clear_search_cache(db: Session, keyword: str, country: str):
    """清除指定关键词+国家的搜索缓存"""
    db.query(SearchCache).filter(
        SearchCache.keyword == keyword,
        SearchCache.country == country,
    ).delete()
    db.commit()


# ──── 官网抓取缓存（7天有效） ────

WEBSITE_CACHE_EXPIRE_DAYS = 7


def _compute_hash(content: str) -> str:
    """计算内容哈希值"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_website_cache(db: Session, website: str) -> Optional[Dict[str, Any]]:
    """
    获取官网抓取缓存
    7天内抓取过的直接返回，不重新抓取
    返回 {"content": ..., "content_hash": ...}
    """
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=WEBSITE_CACHE_EXPIRE_DAYS)
    cached = db.query(WebsiteCache).filter(
        WebsiteCache.website == website,
        WebsiteCache.last_crawled >= cutoff,
    ).first()

    if not cached:
        return None

    return {
        "content": cached.content or "",
        "content_hash": cached.content_hash or "",
    }


def save_website_cache(db: Session, website: str, content: str):
    """保存官网抓取结果到缓存"""
    content_hash = _compute_hash(content)
    now = datetime.datetime.utcnow()

    # 如果已存在则更新
    existing = db.query(WebsiteCache).filter(WebsiteCache.website == website).first()
    if existing:
        existing.content = content
        existing.content_hash = content_hash
        existing.last_crawled = now
    else:
        cache_entry = WebsiteCache(
            website=website,
            content=content,
            content_hash=content_hash,
            last_crawled=now,
        )
        db.add(cache_entry)

    db.commit()


# ──── AI分析缓存（内容未变则复用） ────

def get_analysis_cache(db: Session, website: str, content: str) -> Optional[Dict[str, Any]]:
    """
    获取AI分析缓存
    如果网站内容哈希值相同，说明内容未变化，直接返回缓存的分析结果
    返回 AI 分析结果字典
    """
    content_hash = _compute_hash(content)

    cached = db.query(AnalysisCache).filter(
        AnalysisCache.website == website,
        AnalysisCache.content_hash == content_hash,
    ).first()

    if not cached:
        return None

    result = {
        "company_type": cached.company_type,
        "summary": cached.summary,
        "sales_hook": cached.sales_hook,
        "target_position": cached.target_position,
        "analysis_reason": cached.analysis_reason,
        "identified_projects": cached.identified_projects,
    }

    # 如果保存了原始JSON也返回
    if cached.raw_json:
        try:
            result["raw_json"] = json.loads(cached.raw_json)
        except (json.JSONDecodeError, TypeError):
            pass

    return result


def save_analysis_cache(db: Session, website: str, content: str, ai_result: Dict[str, Any]):
    """保存AI分析结果到缓存"""
    content_hash = _compute_hash(content)

    existing = db.query(AnalysisCache).filter(
        AnalysisCache.website == website,
    ).first()

    now = datetime.datetime.utcnow()

    if existing:
        existing.content_hash = content_hash
        existing.company_type = ai_result.get("company_type", "")
        existing.summary = ai_result.get("summary", "")
        existing.sales_hook = ai_result.get("sales_hook", "")
        existing.target_position = ai_result.get("target_position", "")
        existing.analysis_reason = ai_result.get("analysis_reason", "")
        existing.identified_projects = ai_result.get("identified_projects", "")
        existing.raw_json = json.dumps(ai_result, ensure_ascii=False)
        existing.created_at = now
    else:
        cache_entry = AnalysisCache(
            website=website,
            content_hash=content_hash,
            company_type=ai_result.get("company_type", ""),
            summary=ai_result.get("summary", ""),
            sales_hook=ai_result.get("sales_hook", ""),
            target_position=ai_result.get("target_position", ""),
            analysis_reason=ai_result.get("analysis_reason", ""),
            identified_projects=ai_result.get("identified_projects", ""),
            raw_json=json.dumps(ai_result, ensure_ascii=False),
            created_at=now,
        )
        db.add(cache_entry)

    db.commit()


# ──── 缓存清理（V3.2.2 新增） ────

def clean_expired_cache(db: Session, days_old: int = None) -> dict:
    """
    清理所有过期缓存记录。
    根据各缓存表的 TTL 删除过期数据，防止数据无限堆积。

    参数:
        days_old: 可选覆盖值，删除所有早于 days_old 天的记录。
                  不传则按各表默认 TTL 执行。
    返回:
        各表删除行数的字典
    """
    from app.database import (
        SearchCache, WebsiteCache, AnalysisCache,
        HunterCache, TombaCache, ProspeoCache, EmailQuotaLog,
    )

    now = datetime.datetime.utcnow()
    counts = {}

    def _delete_expired(table, date_column, ttl_days, label):
        cutoff = now - datetime.timedelta(days=days_old if days_old is not None else ttl_days)
        deleted = db.query(table).filter(date_column < cutoff).delete()
        counts[label] = deleted

    _delete_expired(SearchCache, SearchCache.created_at, SEARCH_CACHE_EXPIRE_DAYS, "search_cache")
    _delete_expired(WebsiteCache, WebsiteCache.last_crawled, WEBSITE_CACHE_EXPIRE_DAYS, "website_cache")

    # AI分析缓存：按 content_hash 去重，保留每个网站最新一条，删除旧版本
    cutoff = now - datetime.timedelta(days=days_old if days_old is not None else 90)
    # 先清理 createdAt 过期的孤立记录
    isolated = db.query(AnalysisCache).filter(AnalysisCache.created_at < cutoff).delete()
    counts["analysis_cache_isolated"] = isolated

    # hunter_cache: 按 HUNTER_CACHE_TTL 环境变量（默认 7 天）
    hunter_ttl = int(os.environ.get("HUNTER_CACHE_TTL", str(7 * 24 * 3600))) // 86400
    _delete_expired(HunterCache, HunterCache.created_at, hunter_ttl, "hunter_cache")

    # tomba_cache: 按 TOMBA_CACHE_TTL 环境变量（默认 7 天）
    tomba_ttl = int(os.environ.get("TOMBA_CACHE_TTL", str(7 * 24 * 3600))) // 86400
    _delete_expired(TombaCache, TombaCache.created_at, tomba_ttl, "tomba_cache")

    # prospeo_cache: 按 PROSPEO_CACHE_TTL 环境变量（默认 7 天）
    prospeo_ttl = int(os.environ.get("PROSPEO_CACHE_TTL", str(7 * 24 * 3600))) // 86400
    _delete_expired(ProspeoCache, ProspeoCache.created_at, prospeo_ttl, "prospeo_cache")

    # email_quota_log: 保留 90 天
    _delete_expired(EmailQuotaLog, EmailQuotaLog.created_at, 90, "email_quota_log")

    db.commit()
    return counts
