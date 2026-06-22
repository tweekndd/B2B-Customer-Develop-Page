"""
配置管理 API 路由（V2.8 新增）
允许用户通过网页编辑评分标准、行业关键词、国家权重等配置，实时生效
"""
import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Body

from app.services.scoring_engine import invalidate_config_cache
from app.services.keyword_analyzer import invalidate_keyword_cache

router = APIRouter(tags=["config"])

_CONFIG_DIR = os.path.dirname(os.path.dirname(__file__)) + "/services"
_INDUSTRY_CONFIG_PATH = os.path.join(_CONFIG_DIR, "industry_config.json")
_COUNTRY_WEIGHTS_PATH = os.path.join(_CONFIG_DIR, "country_weights.json")


def _read_json(path: str) -> dict:
    """安全读取 JSON 文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"读取配置文件失败: {e}")


def _write_json(path: str, data: dict, validate_schema: Optional[callable] = None):
    """安全写入 JSON 文件，可选校验"""
    if validate_schema:
        errors = validate_schema(data)
        if errors:
            raise HTTPException(status_code=400, detail=f"配置校验失败: {'; '.join(errors)}")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入配置文件失败: {e}")


# ═══════════════════════════════════════════
# Schema 校验
# ═══════════════════════════════════════════

def _validate_industry_config(cfg: dict) -> list:
    """校验 industry_config.json 的结构，返回错误列表（空=通过）"""
    errors = []

    if not isinstance(cfg, dict):
        return ["根节点必须是对象"]

    # positive_keywords（可选）
    pk = cfg.get("positive_keywords")
    if pk is not None and not isinstance(pk, list):
        errors.append("positive_keywords 必须是数组")

    # negative_keywords（可选）
    nk = cfg.get("negative_keywords")
    if nk is not None and not isinstance(nk, list):
        errors.append("negative_keywords 必须是数组")

    # scoring（可选）
    scoring = cfg.get("scoring", {})
    if not isinstance(scoring, dict):
        errors.append("scoring 必须是对象")
        return errors

    # industry_match
    im = scoring.get("industry_match", {})
    if isinstance(im, dict):
        kws = im.get("keywords", {})
        if kws is not None and not isinstance(kws, dict):
            errors.append("scoring.industry_match.keywords 必须是对象")
        for kw, weight in (kws or {}).items():
            if not isinstance(weight, (int, float)) or weight < 0:
                errors.append(f"关键词权重必须为非负数: {kw}={weight}")
    else:
        errors.append("scoring.industry_match 必须是对象")

    # project_match
    pm = scoring.get("project_match", {})
    if isinstance(pm, dict):
        for key in ("detection_keywords", "content_keywords"):
            val = pm.get(key)
            if val is not None and not isinstance(val, list):
                errors.append(f"scoring.project_match.{key} 必须是数组")
        # 可配置的显示标签（非水处理行业可以自定义）
        for label_key in ("has_project_label", "has_content_label", "low_relevance_label"):
            val = pm.get(label_key)
            if val is not None and not isinstance(val, str):
                errors.append(f"scoring.project_match.{label_key} 必须是字符串")
    else:
        errors.append("scoring.project_match 必须是对象")

    # company_type
    ct = scoring.get("company_type", {})
    if isinstance(ct, dict):
        types = ct.get("types", {})
        if types is not None and not isinstance(types, dict):
            errors.append("scoring.company_type.types 必须是对象")
        for name, score in (types or {}).items():
            if not isinstance(score, (int, float)) or score < 0:
                errors.append(f"公司类型分数必须为非负数: {name}={score}")
    else:
        errors.append("scoring.company_type 必须是对象")

    # contact
    contact = scoring.get("contact", {})
    if isinstance(contact, dict):
        tiers = contact.get("tiers", [])
        if not isinstance(tiers, list):
            errors.append("scoring.contact.tiers 必须是数组")
        else:
            for t in tiers:
                if not isinstance(t, dict):
                    errors.append("tier 必须是对象")
                else:
                    if not isinstance(t.get("min_emails"), int) or t["min_emails"] < 0:
                        errors.append("tier.min_emails 必须是非负整数")
                    if not isinstance(t.get("score"), (int, float)) or t["score"] < 0:
                        errors.append("tier.score 必须是非负数")
    else:
        errors.append("scoring.contact 必须是对象")

    # priority_rules
    pr = cfg.get("priority_rules", {})
    if not isinstance(pr, dict):
        errors.append("priority_rules 必须是对象")
    else:
        for level in ("A", "B", "C", "D"):
            rule = pr.get(level, {})
            if isinstance(rule, dict) and "min" in rule:
                if not isinstance(rule["min"], (int, float)):
                    errors.append(f"priority_rules.{level}.min 必须是数字")

    return errors


def _validate_country_weights(cfg: dict) -> list:
    """校验 country_weights.json，返回错误列表"""
    errors = []
    if not isinstance(cfg, dict):
        return ["根节点必须是对象"]
    for country, weight in cfg.items():
        if not isinstance(weight, (int, float)) or weight < 0 or weight > 100:
            errors.append(f"国家 {country} 的权重必须在 0-100 之间，当前为 {weight}")
    return errors


# ═══════════════════════════════════════════
# API: 获取配置
# ═══════════════════════════════════════════

@router.get("/config")
def get_config():
    """获取完整的评分系统配置（industry_config + country_weights）"""
    return {
        "industry_config": _read_json(_INDUSTRY_CONFIG_PATH),
        "country_weights": _read_json(_COUNTRY_WEIGHTS_PATH),
    }


# ═══════════════════════════════════════════
# API: 保存 industry_config
# ═══════════════════════════════════════════

@router.put("/config")
def save_config(data: dict = Body(...)):
    """
    保存 industry_config.json
    接收完整的配置对象，校验后写入磁盘并清除缓存
    """
    errors = _validate_industry_config(data)
    if errors:
        raise HTTPException(status_code=400, detail=f"配置校验失败: {'; '.join(errors)}")

    _write_json(_INDUSTRY_CONFIG_PATH, data)

    # 清除所有缓存，使新配置即时生效
    invalidate_config_cache()
    invalidate_keyword_cache()

    return {"message": "配置已保存，新评分规则已生效"}


# ═══════════════════════════════════════════
# API: 保存 country_weights
# ═══════════════════════════════════════════

@router.put("/config/country-weights")
def save_country_weights(data: dict = Body(...)):
    """
    保存 country_weights.json
    接收完整的国家权重对象，校验后写入磁盘并清除缓存
    """
    errors = _validate_country_weights(data)
    if errors:
        raise HTTPException(status_code=400, detail=f"国家权重校验失败: {'; '.join(errors)}")

    _write_json(_COUNTRY_WEIGHTS_PATH, data)

    # 清除评分缓存
    invalidate_config_cache()

    return {"message": "国家权重已保存，新评分规则已生效"}
