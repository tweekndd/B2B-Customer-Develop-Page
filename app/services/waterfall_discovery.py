"""
瀑布式邮箱发现服务（Phase 1 新增）
多数据源级联查找：Hunter → Tomba → 自研抓取兜底

核心逻辑：
1. 先查 Hunter（已有数据源，保留为第一优先级）
2. Hunter 无结果或数量不足 → 查 Tomba
3. Tomba 仍无结果 → 自研官网抓取 mailto: 兜底
4. 结果合并 → 去重 → 排序 → 输出
"""
import os
import re
import json
import datetime
import logging
from typing import List, Dict, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.database import EmailQuotaLog

logger = logging.getLogger(__name__)

# ── 配置 ──
# 结果数低于此值才触发下一级
MIN_RESULTS = int(os.environ.get("EMAIL_DISCOVERY_MIN_RESULTS", "2"))
# 是否启用自研抓取兜底
ENABLE_SCRAPING = os.environ.get("EMAIL_DISCOVERY_ENABLE_SCRAPING", "true").lower() == "true"

# 通用邮箱黑名单（不纳入结果）
GENERIC_BLACKLIST = {
    "info", "support", "noreply", "no-reply", "admin", "webmaster",
    "postmaster", "contact", "help", "hello", "careers", "jobs",
    "abuse", "privacy", "legal", "press", "media", "newsletter",
}


def _extract_domain(website: str) -> str:
    """从网址中提取域名"""
    if not website:
        return ""
    domain = website.strip().lower()
    domain = re.sub(r"^https?://", "", domain)
    domain = domain.split("/")[0]
    domain = domain.split("?")[0]
    return domain


# ═══════════════════════════════════════════
# 统一结果格式
# ═══════════════════════════════════════════

def _make_email_entry(
    email: str,
    source: str,
    first_name: str = "",
    last_name: str = "",
    position: str = "",
    department: str = "",
    phone: str = "",
    linkedin: str = "",
    score: int = 0,
    verification: str = "",
) -> dict:
    """创建统一格式的邮箱条目"""
    return {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "full_name": f"{first_name} {last_name}".strip(),
        "position": position,
        "department": department,
        "phone": phone,
        "linkedin": linkedin,
        "score": score,
        "verification": verification,
        "source": source,  # hunter / tomba / scraped
    }


# ═══════════════════════════════════════════
# 第1级：Hunter 查找
# ═══════════════════════════════════════════

async def _hunter_discovery(domain: str, db: Session) -> List[Dict]:
    """通过 Hunter 查找邮箱"""
    from app.services.hunter_service import HunterClient, HUNTER_API_KEY

    if not HUNTER_API_KEY:
        logger.info("[瀑布] Hunter 未配置 API Key，跳过")
        return []

    try:
        client = HunterClient(db=db)
        result = client.smart_find_emails(domain=domain)
        emails_raw = result.get("emails", [])

        if not emails_raw:
            logger.info(f"[瀑布] Hunter 在 {domain} 未找到邮箱")
            return []

        entries = []
        for e in emails_raw:
            email_val = e.get("value") or e.get("email", "")
            if not email_val:
                continue
            entries.append(_make_email_entry(
                email=email_val,
                source="hunter",
                first_name=e.get("first_name", ""),
                last_name=e.get("last_name", ""),
                position=e.get("position", ""),
                department=e.get("department", ""),
                score=e.get("confidence", 50),
                verification=e.get("verification", {}).get("status", ""),
            ))

        logger.info(f"[瀑布] Hunter 在 {domain} 找到 {len(entries)} 个邮箱")
        return entries

    except Exception as e:
        logger.warning(f"[瀑布] Hunter 查询异常: {e}")
        return []


# ═══════════════════════════════════════════
# 第2级：Tomba 查找
# ═══════════════════════════════════════════

async def _tomba_discovery(domain: str, db: Session) -> List[Dict]:
    """通过 Tomba 查找邮箱"""
    from app.services.tomba_service import TombaClient, TOMBA_API_KEY, TOMBA_API_SECRET

    if not TOMBA_API_KEY or not TOMBA_API_SECRET:
        logger.info("[瀑布] Tomba 未配置 API Key/Secret，跳过")
        return []

    try:
        client = TombaClient(db=db)
        data = client.domain_search(domain=domain, limit=50)
        emails_raw = data.get("data", {}).get("emails", [])

        if not emails_raw:
            logger.info(f"[瀑布] Tomba 在 {domain} 未找到邮箱")
            return []

        entries = []
        for e in emails_raw:
            email_val = e.get("email", "")
            if not email_val:
                continue
            entries.append(_make_email_entry(
                email=email_val,
                source="tomba",
                first_name=e.get("first_name", ""),
                last_name=e.get("last_name", ""),
                position=e.get("position", ""),
                department=e.get("department", ""),
                phone=e.get("phone_number") or "",
                linkedin=e.get("linkedin") or "",
                score=e.get("score", 50),
                verification=e.get("verification", {}).get("status", ""),
            ))

        logger.info(f"[瀑布] Tomba 在 {domain} 找到 {len(entries)} 个邮箱")
        return entries

    except Exception as e:
        logger.warning(f"[瀑布] Tomba 查询异常: {e}")
        return []


# ═══════════════════════════════════════════
# 第3级：自研网页抓取兜底
# ═══════════════════════════════════════════

async def _scrape_discovery(domain: str) -> List[Dict]:
    """从官网 HTML 提取 mailto: 链接作为兜底"""
    if not ENABLE_SCRAPING:
        logger.info("[瀑布] 自研抓取兜底已禁用（EMAIL_DISCOVERY_ENABLE_SCRAPING=false）")
        return []

    urls_to_try = [f"https://{domain}", f"https://www.{domain}"]
    found_emails = set()
    results = []

    for base_url in urls_to_try:
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            }
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(base_url, headers=headers)
                if resp.status_code != 200:
                    continue
                if "text/html" not in resp.headers.get("content-type", ""):
                    continue

                # 使用 BeautifulSoup 提取 mailto: 链接和明文邮箱
                soup = BeautifulSoup(resp.text, "html.parser")

                # 1. mailto: 链接
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    if href.startswith("mailto:"):
                        email = href[7:].split("?")[0].strip()
                        if email and "@" in email and email not in found_emails:
                            found_emails.add(email)
                            # 检查附近有没有姓名信息
                            parent_text = a_tag.parent.get_text(strip=True) if a_tag.parent else ""
                            results.append(_make_email_entry(
                                email=email,
                                source="scraped",
                                full_name=parent_text[:50] if parent_text and len(parent_text) < 50 else "",
                                score=30,  # 自研抓取置信度较低
                            ))

                # 2. 明文邮箱（正则提取）
                email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
                for match in email_pattern.finditer(resp.text):
                    email = match.group(0).lower()
                    # 过滤掉图片域名等无关内容
                    if any(ext in email for ext in [".png", ".jpg", ".gif", ".svg", ".css", ".js"]):
                        continue
                    # 过滤掉 @ 后是图片/资源域名的
                    email_domain = email.split("@")[-1]
                    if email_domain == domain or email_domain.endswith("." + domain):
                        pass  # 同一域名下的邮箱保留
                    elif email_domain != domain:
                        continue  # 不同域名跳过
                    if email in found_emails:
                        continue
                    # 过滤通用邮箱
                    local_part = email.split("@")[0].lower()
                    if local_part in GENERIC_BLACKLIST:
                        continue
                    found_emails.add(email)
                    results.append(_make_email_entry(
                        email=email,
                        source="scraped",
                        score=25,  # 明文抓取置信度更低
                    ))

                logger.info(f"[瀑布] 自研抓取 {base_url} 找到 {len(results)} 个邮箱")
                break  # 成功抓取一个 URL 即可

        except Exception as e:
            logger.warning(f"[瀑布] 自研抓取 {base_url} 失败: {e}")
            continue

    return results


# ═══════════════════════════════════════════
# 合并与去重
# ═══════════════════════════════════════════

def _merge_and_dedup(all_entries: List[List[Dict]]) -> List[Dict]:
    """
    合并多源结果，按邮箱去重
    同一邮箱保留置信度最高的那条记录（优先级：tomba > hunter > scraped）
    """
    seen = {}  # email -> entry
    source_priority = {"tomba": 3, "hunter": 2, "scraped": 1}

    for source_entries in all_entries:
        for entry in source_entries:
            email = entry["email"].lower().strip()
            if not email:
                continue
            existing = seen.get(email)
            if existing:
                # 保留置信度高的来源
                existing_priority = source_priority.get(existing["source"], 0)
                new_priority = source_priority.get(entry["source"], 0)
                if new_priority > existing_priority:
                    seen[email] = entry
                elif new_priority == existing_priority and entry.get("score", 0) > existing.get("score", 0):
                    seen[email] = entry
            else:
                seen[email] = entry

    return list(seen.values())


# ═══════════════════════════════════════════
# 评分排序
# ═══════════════════════════════════════════

def _score_and_sort(entries: List[Dict]) -> List[Dict]:
    """
    对邮箱按综合得分排序输出
    得分维度：来源权重 + 验证状态 + 职位级别 + 置信度分数
    """
    source_weight = {"tomba": 30, "hunter": 25, "scraped": 10}
    verification_weight = {"valid": 30, "unknown": 15, "": 0}
    position_keywords = {
        "ceo": 30, "cto": 30, "coo": 28, "cfo": 28, "vp": 25,
        "director": 22, "manager": 18, "head": 20, "chief": 28,
        "president": 28, "owner": 25, "founder": 25, "partner": 22,
    }

    for entry in entries:
        score = 0
        # 来源权重
        score += source_weight.get(entry.get("source", ""), 5)
        # 验证状态
        score += verification_weight.get(entry.get("verification", ""), 0)
        # 职位级别
        position = (entry.get("position", "") or "").lower()
        for kw, pts in position_keywords.items():
            if kw in position:
                score += pts
                break
        # 置信度分数（0-100 映射到 0-20）
        score += min(20, max(0, (entry.get("score", 0) / 100) * 20))

        entry["_sort_score"] = score

    entries.sort(key=lambda e: e.get("_sort_score", 0), reverse=True)

    # 移除排序辅助字段
    for entry in entries:
        entry.pop("_sort_score", None)

    return entries


# ═══════════════════════════════════════════
# 配额记录（持久化）
# ═══════════════════════════════════════════

def _log_waterfall_usage(
    db: Session, domain: str, source: str,
    result_count: int, credits: int = 0,
    success: bool = True, error: str = "",
):
    """记录瀑布式调用的配额使用"""
    if not db:
        return
    try:
        log = EmailQuotaLog(
            source=source,
            query_type="waterfall",
            domain=domain,
            result_count=result_count,
            credits_consumed=credits,
            success=1 if success else 0,
            error_message=error or None,
            created_at=datetime.datetime.utcnow(),
        )
        db.add(log)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"[瀑布] 配额记录写入失败: {e}")


# ═══════════════════════════════════════════
# 瀑布式入口（对外暴露的唯一接口）
# ═══════════════════════════════════════════

async def waterfall_email_discovery(
    website: str,
    db: Session = None,
) -> dict:
    """
    瀑布式邮箱发现入口

    调用链：Hunter → Tomba → 自研抓取兜底
    只有上一级无结果或结果少于 MIN_RESULTS 时才触发下一级

    Args:
        website: 公司网址/域名
        db: 数据库会话（可选，用于缓存和配额记录）

    Returns:
        {
            "domain": "xxx",
            "total": N,
            "emails": [...],
            "sources_used": ["hunter", "tomba"],
            "waterfall_log": [...],
        }
    """
    domain = _extract_domain(website)
    if not domain:
        return {"domain": "", "total": 0, "emails": [], "sources_used": [], "waterfall_log": []}

    all_entries = []
    sources_used = []
    log = []

    # ── 第1级：Hunter ──
    logger.info(f"[瀑布] 第1级 Hunter 开始查询 {domain}")
    hunter_entries = await _hunter_discovery(domain, db)
    all_entries.append(hunter_entries)
    log.append({"source": "hunter", "found": len(hunter_entries), "triggered_next": len(hunter_entries) < MIN_RESULTS})
    if hunter_entries:
        sources_used.append("hunter")

    # ── 判断是否触发第2级 ──
    if len(hunter_entries) < MIN_RESULTS:
        logger.info(f"[瀑布] 第2级 Tomba 开始查询 {domain} (Hunter 仅 {len(hunter_entries)} 条)")
        tomba_entries = await _tomba_discovery(domain, db)
        all_entries.append(tomba_entries)
        log.append({"source": "tomba", "found": len(tomba_entries), "triggered_next": len(tomba_entries) < MIN_RESULTS})
        if tomba_entries:
            sources_used.append("tomba")

        # ── 判断是否触发第3级 ──
        total_so_far = len(hunter_entries) + len(tomba_entries)
        if total_so_far < MIN_RESULTS:
            logger.info(f"[瀑布] 第3级 自研抓取开始 {domain} (前两级共 {total_so_far} 条)")
            scraped_entries = await _scrape_discovery(domain)
            all_entries.append(scraped_entries)
            log.append({"source": "scraped", "found": len(scraped_entries), "triggered_next": False})
            if scraped_entries:
                sources_used.append("scraped")
        else:
            log.append({"source": "scraped", "found": 0, "triggered_next": False, "skipped": True})
    else:
        log.append({"source": "tomba", "found": 0, "triggered_next": False, "skipped": True})
        log.append({"source": "scraped", "found": 0, "triggered_next": False, "skipped": True})

    # ── 合并去重 ──
    merged = _merge_and_dedup(all_entries)

    # ── 评分排序 ──
    sorted_entries = _score_and_sort(merged)

    # ── 记录配额 ──
    for src in sources_used:
        src_emails = [e for e in sorted_entries if e.get("source") == src]
        _log_waterfall_usage(db, domain, src, len(src_emails))

    result = {
        "domain": domain,
        "total": len(sorted_entries),
        "emails": sorted_entries,
        "sources_used": sources_used,
        "waterfall_log": log,
    }

    logger.info(f"[瀑布] {domain} 完成: 共 {len(sorted_entries)} 个邮箱，来源: {sources_used}")
    return result
