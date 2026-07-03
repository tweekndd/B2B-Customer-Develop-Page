"""
Hunter 邮箱查找 API 路由（V3.0 新增）
提供邮箱查找、配额查询、缓存管理接口
"""
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db, HunterCache
from app.services.hunter_service import (
    HunterClient,
    HunterError,
    clear_hunter_cache,
    HUNTER_API_KEY,
)
from app.auth import check_email_finding_permission

router = APIRouter(tags=["hunter"])


def _get_hunter_client(db: Session = Depends(get_db)) -> HunterClient:
    """依赖注入：获取 Hunter 客户端"""
    try:
        return HunterClient(db=db)
    except HunterError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


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
# 配置状态
# ═══════════════════════════════════════════

@router.get("/hunter/status")
def get_hunter_status():
    """获取 Hunter 功能状态（API Key 是否已配置、是否为测试模式）"""
    configured = bool(HUNTER_API_KEY)
    return {
        "configured": configured,
        "test_mode": HUNTER_API_KEY == "test-api-key",
        "message": "已配置" if configured else "未配置（请在环境变量设置 HUNTER_API_KEY）",
    }


# ═══════════════════════════════════════════
# 邮箱数量预览（免费）
# ═══════════════════════════════════════════

@router.get("/hunter/email-count")
def api_email_count(
    domain: str = Query(..., description="公司域名，如 stripe.com"),
    force_refresh: bool = Query(False, description="强制刷新（跳过缓存）"),
    db: Session = Depends(get_db),
    user=Depends(check_email_finding_permission),
):
    """查询域名下的邮箱总量（免费，不消耗搜索额度）"""
    try:
        client = HunterClient(db=db)
        data = client.email_count(domain, force_refresh=force_refresh)
        count_info = data.get("data", {})
        return {
            "domain": domain,
            "total": count_info.get("total", 0),
            "personal_emails": count_info.get("personal_emails", 0),
            "generic_emails": count_info.get("generic_emails", 0),
            "department": count_info.get("department", {}),
            "seniority": count_info.get("seniority", {}),
            "from_cache": data.get("_cache", False),
        }
    except HunterError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


# ═══════════════════════════════════════════
# 智能查找邮箱
# ═══════════════════════════════════════════

@router.get("/hunter/find-emails")
def api_find_emails(
    website: str = Query(None, description="公司网址，如 https://stripe.com"),
    domain: str = Query(None, description="公司域名（与 website 二选一，优先级更高）"),
    company_name: str = Query(None, description="公司名称（仅用于展示）"),
    first_name: str = Query(None, description="联系人名（可选）"),
    last_name: str = Query(None, description="联系人姓（可选）"),
    user=Depends(check_email_finding_permission),
    full_name: str = Query(None, description="联系人全名（可选，自动拆分）"),
    department: str = Query(None, description="部门筛选: executive/it/finance/sales/marketing/hr/legal/support"),
    seniority: str = Query(None, description="级别筛选: junior/senior/executive"),
    force_refresh: bool = Query(False, description="强制刷新（跳过缓存）"),
    db: Session = Depends(get_db),
):
    """
    智能查找公司邮箱（自动应用额度优化策略）

    查找策略：
    1. 先查 Email Count（免费）→ 如无数据直接返回
    2. 有姓名 → 优先 Domain Search 缓存中匹配 → 失败降级 Email Finder
    3. 无姓名 → Domain Search 全量搜索
    4. 结果自带验证状态，无需额外调用 Verifier
    """
    # 解析域名
    domain_to_use = domain or ""
    if not domain_to_use and website:
        domain_to_use = _extract_domain(website)
    domain_to_use = domain_to_use.strip().lower()
    if not domain_to_use:
        raise HTTPException(status_code=400, detail="请提供 domain 或 website")

    # 解析姓名
    fn = first_name
    ln = last_name
    if full_name and not fn and not ln:
        parts = full_name.strip().split(None, 1)
        fn = parts[0] if len(parts) > 0 else None
        ln = parts[1] if len(parts) > 1 else None

    try:
        client = HunterClient(db=db)
        result = client.smart_find_emails(
            domain=domain_to_use,
            first_name=fn,
            last_name=ln,
        )

        # 如果有部门/级别筛选，在结果中过滤
        emails = result.get("emails", [])
        if department:
            emails = [e for e in emails if (e.get("department") or "").lower() == department.lower()]
        if seniority:
            emails = [e for e in emails if (e.get("seniority") or "").lower() == seniority.lower()]

        return {
            "domain": domain_to_use,
            "company_name": company_name or "",
            "source": result.get("source"),
            "total_available": result.get("total_available", 0),
            "emails": emails,
            "email_count": len(emails),
            "quota_used": result.get("quota_used", {}),
        }
    except HunterError as e:
        # 404 是正常找不到，不是错误
        if e.status_code == 404:
            return {
                "domain": domain_to_use,
                "company_name": company_name or "",
                "source": None,
                "total_available": 0,
                "emails": [],
                "email_count": 0,
                "note": "Hunter 数据库中未找到该公司邮箱数据",
            }
        raise HTTPException(status_code=e.status_code, detail=str(e))


# ═══════════════════════════════════════════
# 精确查询某人
# ═══════════════════════════════════════════

@router.get("/hunter/find-person")
def api_find_person(
    website: str = Query(None, description="公司网址"),
    domain: str = Query(None, description="公司域名（与 website 二选一）"),
    first_name: str = Query(..., description="名"),
    last_name: str = Query(..., description="姓"),
    force_refresh: bool = Query(False),
    db: Session = Depends(get_db),
    user=Depends(check_email_finding_permission),
):
    """
    精确查找特定人员的邮箱
    直接调用 Email Finder API，适合已知姓名和公司的场景
    """
    domain_to_use = domain or ""
    if not domain_to_use and website:
        domain_to_use = _extract_domain(website)
    domain_to_use = domain_to_use.strip().lower()
    if not domain_to_use:
        raise HTTPException(status_code=400, detail="请提供 domain 或 website")

    try:
        client = HunterClient(db=db)
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
                "position": person.get("position", ""),
                "confidence": person.get("confidence", 0),
                "verification": person.get("verification", {}),
                "sources": person.get("sources", []),
            }
        return {
            "found": False,
            "domain": domain_to_use,
            "first_name": first_name,
            "last_name": last_name,
            "email": None,
            "note": "未找到该人员的邮箱（Hunter 数据库无匹配数据，这次查询不扣费）",
        }
    except HunterError as e:
        if e.status_code == 404:
            return {
                "found": False,
                "domain": domain_to_use,
                "first_name": first_name,
                "last_name": last_name,
                "email": None,
                "note": "未找到该人员的邮箱（Hunter 数据库无匹配数据，本次查询不扣费）",
            }
        raise HTTPException(status_code=e.status_code, detail=str(e))


# ═══════════════════════════════════════════
# 缓存管理 & 配额
# ═══════════════════════════════════════════

@router.get("/hunter/usage")
def api_hunter_usage(db: Session = Depends(get_db)):
    """获取 Hunter 配额使用统计"""
    stats = {
        "session_usage": {
            "email_count": 0,
            "domain_search": 0,
            "email_finder": 0,
            "email_verifier": 0,
            "cache_hits": 0,
            "total_searches": 0,
            "total_verifications": 0,
            "total_api_calls": 0,
        },
        "cache": {"enabled": False},
        "configured": bool(HUNTER_API_KEY),
    }
    try:
        client = HunterClient(db=db)
        stats["session_usage"] = client.get_usage_stats()
        stats["cache"] = client.get_cache_stats()
    except HunterError as e:
        stats["error"] = str(e)
    return stats


@router.post("/hunter/clear-cache")
def api_clear_hunter_cache(db: Session = Depends(get_db)):
    """清除所有 Hunter 缓存，下次查询将调用真实 API"""
    try:
        count = clear_hunter_cache(db)
        return {"message": f"已清除 {count} 条 Hunter 缓存", "cleared": count}
    except Exception as e:
        return {"message": f"缓存表尚未创建: {e}", "cleared": 0}


@router.get("/hunter/cache-entries")
def api_list_cache_entries(db: Session = Depends(get_db)):
    """列出所有 Hunter 缓存条目"""
    try:
        entries = db.query(HunterCache).order_by(HunterCache.created_at.desc()).limit(100).all()
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

