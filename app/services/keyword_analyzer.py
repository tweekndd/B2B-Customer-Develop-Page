"""
关键词识别服务（V2.8 更新）
从 industry_config.json 读取正向/负向关键词，支持运行时修改无需重启
"""
import json
import os
import re
from typing import Dict, List, Tuple
from functools import lru_cache


# V2.8 前向兼容：如果 industry_config.json 中未定义关键词，使用以下默认值
_FALLBACK_POSITIVE = [
    "wastewater", "water treatment", "sewage", "effluent",
    "biogas", "anaerobic", "digester", "tank", "storage tank",
    "reservoir", "municipal water", "desalination", "irrigation",
    "industrial water",
]
_FALLBACK_NEGATIVE = [
    "career", "job", "vacancy", "news", "blog", "school", "university",
]

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "industry_config.json")


@lru_cache(maxsize=1)
def _load_keywords() -> dict:
    """从 industry_config.json 加载关键词列表（缓存 1 次，API 写入后自动清除）"""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def invalidate_keyword_cache():
    """清除关键词缓存，配置写入后由 API 调用"""
    _load_keywords.cache_clear()


def _get_positive_keywords() -> List[str]:
    """获取正向关键词列表，优先从配置文件读取"""
    config = _load_keywords()
    kws = config.get("positive_keywords")
    return list(kws) if kws else list(_FALLBACK_POSITIVE)


def _get_negative_keywords() -> List[str]:
    """获取负向关键词列表，优先从配置文件读取"""
    config = _load_keywords()
    kws = config.get("negative_keywords")
    return list(kws) if kws else list(_FALLBACK_NEGATIVE)


def analyze_keywords(text: str) -> Tuple[Dict[str, int], Dict[str, int]]:
    """
    分析文本中关键词的命中情况
    返回 (正向关键词计数字典, 负向关键词计数字典)
    """
    if not text:
        return {}, {}

    text_lower = text.lower()

    positive_hits = _count_keywords(text_lower, _get_positive_keywords())
    negative_hits = _count_keywords(text_lower, _get_negative_keywords())

    return positive_hits, negative_hits


def _count_keywords(text: str, keywords: List[str]) -> Dict[str, int]:
    """统计一组关键词在文本中的出现次数"""
    result = {}
    for keyword in keywords:
        if " " in keyword:
            # 多词关键词，直接查找子串
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        else:
            # 单次关键词：使用单词边界确保完整匹配
            pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)

        count = len(pattern.findall(text))
        if count > 0:
            result[keyword] = count

    # 按次数降序排序
    return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))
