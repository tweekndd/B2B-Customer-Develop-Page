"""
瀑布式邮箱发现 API 路由（Phase 1 新增 | V3.2.2 加入 Prospeo）
多源级联查找：Hunter → Tomba → Prospeo → 自研抓取兜底
"""
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db, EmailQuotaLog
from app.services.waterfall_discovery import waterfall_email_discovery
from app.services.prospeo_service import PROSPEO_API_KEY

router = APIRouter(tags=["waterfall"])


@router.get("/waterfall/email-discovery")
async def api_waterfall_discovery(
    website: str = Query(..., description="公司网址或域名，如 https://stripe.com"),
    db: Session = Depends(get_db),
):
    """
    瀑布式邮箱发现

    调用链：Hunter → Tomba → Prospeo → 自研抓取兜底
    只有上一级无结果或结果不足时才触发下一级

    返回结果按综合得分排序：
    - 来源权重：Tomba > Prospeo > Hunter > 自研抓取
    - 验证状态：valid > unknown
    - 职位级别：决策人 > 普通员工 > 通用邮箱
    - 置信度分数
    """
    if not website or not website.strip():
        raise HTTPException(status_code=400, detail="请提供公司网址或域名")

    result = await waterfall_email_discovery(website.strip(), db=db)
    return result


@router.get("/waterfall/prospeo-status")
def get_prospeo_status():
    """获取 Prospeo 功能状态（API Key 是否已配置）"""
    configured = bool(PROSPEO_API_KEY)
    return {
        "configured": configured,
        "message": "已配置" if configured else "未配置（请在环境变量设置 PROSPEO_API_KEY）",
    }


@router.get("/waterfall/quota-history")
def api_waterfall_quota_history(
    source: str = Query(None, description="筛选数据源: hunter/tomba/prospeo/scraped"),
    limit: int = Query(50, description="返回记录数"),
    db: Session = Depends(get_db),
):
    """获取所有邮箱发现源的配额使用历史"""
    query = db.query(EmailQuotaLog).order_by(EmailQuotaLog.created_at.desc())
    if source:
        query = query.filter(EmailQuotaLog.source == source)
    logs = query.limit(limit).all()
    return {
        "logs": [
            {
                "id": log.id,
                "source": log.source,
                "query_type": log.query_type,
                "domain": log.domain,
                "result_count": log.result_count,
                "credits_consumed": log.credits_consumed,
                "success": log.success,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
        "total": len(logs),
    }
