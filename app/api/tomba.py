"""
Tomba 邮箱查找 API 路由（Phase 1 新增）
提供域名搜索、配置状态、配额查询、缓存管理接口
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db, TombaCache
from app.services.tomba_service import (
    TombaClient,
    TombaError,
    clear_tomba_cache,
    TOMBA_API_KEY,
    TOMBA_API_SECRET,
)
from app.auth import check_email_finding_permission

router = APIRouter(tags=["tomba"])


def _extract_domain(website: str) -> str:
    """从网址中提取域名"""
    if not website:
        return ""
    import re
    domain = website.strip().lower()
    domain = re.sub(r"^https?://", "", domain)
    domain = domain.split("/")[0]
    domain = domain.split("?")[0]
    return domain


# ═══════════════════════════════════════════
# 配置状态
# ═══════════════════════════════════════════

@router.get("/tomba/status")
def get_tomba_status():
    """获取 Tomba 功能状态（API Key/Secret 是否已配置）"""
    configured = bool(TOMBA_API_KEY) and bool(TOMBA_API_SECRET)
    return {
        "configured": configured,
        "message": "已配置" if configured else "未配置（请在环境变量设置 TOMBA_API_KEY 和 TOMBA_API_SECRET）",
    }


# ═══════════════════════════════════════════
# 域名搜索
# ═══════════════════════════════════════════

@router.get("/tomba/domain-search")
def api_tomba_domain_search(
    website: str = Query(None, description="公司网址，如 https://stripe.com"),
    domain: str = Query(None, description="公司域名（与 website 二选一，优先级更高）"),
    limit: int = Query(10, description="每页结果数: 10/20/50"),
    page: int = Query(1, description="页码"),
    country: str = Query(None, description="国家筛选（两位字母代码，如 US）"),
    department: str = Query(None, description="部门筛选: engineering/sales/finance/hr/it/marketing/operations/management"),
    enrich_mobile: bool = Query(False, description="是否获取电话号码"),
    force_refresh: bool = Query(False, description="强制刷新（跳过缓存）"),
    db: Session = Depends(get_db),
    user=Depends(check_email_finding_permission),
):
    """
    Tomba 域名搜索（消耗搜索额度，无结果不扣费）

    返回数据包含：
    - 组织信息（描述、员工数、行业、位置、社交链接）
    - 邮箱列表（含姓名、职位、部门、领英、电话、置信度评分）
    """
    domain_to_use = domain or ""
    if not domain_to_use and website:
        domain_to_use = _extract_domain(website)
    domain_to_use = domain_to_use.strip().lower()
    if not domain_to_use:
        raise HTTPException(status_code=400, detail="请提供 domain 或 website")

    if limit not in (10, 20, 50):
        limit = 10

    try:
        client = TombaClient(db=db)
        data = client.domain_search(
            domain=domain_to_use,
            page=page,
            limit=limit,
            country=country,
            department=department,
            enrich_mobile=enrich_mobile,
            force_refresh=force_refresh,
        )

        org = data.get("data", {}).get("organization", {})
        emails = data.get("data", {}).get("emails", [])
        meta = data.get("meta", {})

        return {
            "domain": domain_to_use,
            "organization": {
                "name": org.get("organization", ""),
                "description": org.get("description", ""),
                "employee_count": org.get("employee_count"),
                "company_size": org.get("company_size", ""),
                "industry": org.get("industries", ""),
                "founded": org.get("founded"),
                "revenue": org.get("revenue", ""),
                "location": org.get("location", {}),
                "linkedin": org.get("social_links", {}).get("linkedin_url", ""),
                "twitter": org.get("social_links", {}).get("twitter_url", ""),
                "phone": org.get("phone_number", ""),
            },
            "emails": [
                {
                    "email": e.get("email", ""),
                    "first_name": e.get("first_name", ""),
                    "last_name": e.get("last_name", ""),
                    "full_name": e.get("full_name", ""),
                    "position": e.get("position", ""),
                    "department": e.get("department", ""),
                    "seniority": e.get("seniority", ""),
                    "phone": e.get("phone_number"),
                    "linkedin": e.get("linkedin"),
                    "score": e.get("score", 0),
                    "verification": e.get("verification", {}).get("status"),
                    "sources": e.get("sources", []),
                }
                for e in emails
            ],
            "meta": {
                "total": meta.get("total", 0),
                "page": meta.get("current", 0) + 1,
                "page_size": meta.get("pageSize", limit),
                "total_pages": meta.get("total_pages", 0),
            },
            "email_count": len(emails),
        }
    except TombaError as e:
        if e.status_code in (404, 400):
            return {
                "domain": domain_to_use,
                "organization": {},
                "emails": [],
                "meta": {"total": 0},
                "email_count": 0,
                "note": "Tomba 数据库中未找到该公司数据",
            }
        raise HTTPException(status_code=e.status_code, detail=str(e))


# ═══════════════════════════════════════════
# 精确查询某人
# ═══════════════════════════════════════════

@router.get("/tomba/find-person")
def api_tomba_find_person(
    website: str = Query(None, description="公司网址"),
    domain: str = Query(None, description="公司域名（与 website 二选一）"),
    first_name: str = Query(..., description="名"),
    last_name: str = Query(..., description="姓"),
    force_refresh: bool = Query(False),
    db: Session = Depends(get_db),
    user=Depends(check_email_finding_permission),
):
    """
    精确查找特定人员的邮箱（消耗搜索额度，找不到不扣费）
    """
    domain_to_use = domain or ""
    if not domain_to_use and website:
        domain_to_use = _extract_domain(website)
    domain_to_use = domain_to_use.strip().lower()
    if not domain_to_use:
        raise HTTPException(status_code=400, detail="请提供 domain 或 website")

    try:
        client = TombaClient(db=db)
        data = client.email_finder(
            domain=domain_to_use,
            first_name=first_name,
            last_name=last_name,
            force_refresh=force_refresh,
        )
        person = data.get("data", {})
        if person.get("email"):
            return {
                "found": True,
                "domain": domain_to_use,
                "email": person["email"],
                "first_name": person.get("first_name", first_name),
                "last_name": person.get("last_name", last_name),
                "full_name": person.get("full_name", ""),
                "position": person.get("position", ""),
                "department": person.get("department", ""),
                "phone": person.get("phone_number"),
                "linkedin": person.get("linkedin"),
                "score": person.get("score", 0),
                "sources": person.get("sources", []),
            }
        return {
            "found": False,
            "domain": domain_to_use,
            "first_name": first_name,
            "last_name": last_name,
            "email": None,
            "note": "未找到该人员的邮箱（Tomba 数据库无匹配数据，本次查询不扣费）",
        }
    except TombaError as e:
        if e.status_code == 404:
            return {
                "found": False,
                "domain": domain_to_use,
                "first_name": first_name,
                "last_name": last_name,
                "email": None,
                "note": "未找到该人员的邮箱（Tomba 数据库无匹配数据，本次查询不扣费）",
            }
        raise HTTPException(status_code=e.status_code, detail=str(e))


# ═══════════════════════════════════════════
# 缓存管理 & 配额
# ═══════════════════════════════════════════

@router.get("/tomba/usage")
def api_tomba_usage(db: Session = Depends(get_db)):
    """获取 Tomba 配额使用统计"""
    stats = {
        "session_usage": {
            "domain_search": 0,
            "email_finder": 0,
            "email_verifier": 0,
            "cache_hits": 0,
            "no_result_credits_saved": 0,
            "total_searches": 0,
            "total_api_calls": 0,
        },
        "cache": {"enabled": False},
        "configured": bool(TOMBA_API_KEY) and bool(TOMBA_API_SECRET),
    }
    try:
        client = TombaClient(db=db)
        stats["session_usage"] = client.get_usage_stats()
        stats["cache"] = client.get_cache_stats()
        stats["quota_history"] = client.get_quota_history(20)
    except TombaError as e:
        stats["error"] = str(e)
    return stats


@router.post("/tomba/clear-cache")
def api_clear_tomba_cache(db: Session = Depends(get_db)):
    """清除所有 Tomba 缓存，下次查询将调用真实 API"""
    try:
        count = clear_tomba_cache(db)
        return {"message": f"已清除 {count} 条 Tomba 缓存", "cleared": count}
    except Exception as e:
        return {"message": f"缓存表尚未创建: {e}", "cleared": 0}


@router.get("/tomba/cache-entries")
def api_list_cache_entries(db: Session = Depends(get_db)):
    """列出所有 Tomba 缓存条目"""
    try:
        entries = db.query(TombaCache).order_by(TombaCache.created_at.desc()).limit(100).all()
        return {
            "entries": [
                {
                    "domain": e.domain,
                    "query_type": e.query_type,
                    "hits": e.hits or 0,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in entries
            ],
            "total": len(entries),
        }
    except Exception as e:
        return {"entries": [], "total": 0, "error": str(e)}
