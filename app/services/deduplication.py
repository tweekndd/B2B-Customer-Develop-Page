"""
去重工具服务（V2.6 新增）
提供公司名称标准化、相似度判断、数据库查重等功能
用于搜索发现、Excel导入、相似客户扩展等多个入口的去重
"""
import re
from typing import Optional
from sqlalchemy.orm import Session
from app.database import Customer
from app.services.url_normalizer import normalize_url


# 标准化公司名时要移除的常见法律实体后缀
_LEGAL_SUFFIXES = [
    # ⚠️ 顺序敏感：复合后缀必须排在简单后缀前面！
    # 例如 S.A. de C.V. 要在 S.A. 之前，否则会被拆解

    # 西班牙语/西语国家复合后缀（优先匹配）
    r'\bs\.?a\.?\s+de\s+c\.?v\.?\b', r'\bs\.?a\.?\s+de\s+c\.?v\b',
    r'\bs\.?\s?de\s+r\.?l\.?\b', r'\bs\.?\s?de\s+r\.?l\b',
    r'\be\.?i\.?r\.?l\.?\b', r'\bs\.?a\.?\s+s\.?i\.?\b',
    r'\bsociedad\s+anónima\b', r'\bsociedad\s+limitada\b',
    # 葡萄牙语
    r'\bltda\.?\b', r'\bme\b', r'\bepp\b',
    # 法语
    r'\bsarl\b', r'\beurl\b',
    # 德语
    r'\bkg\b', r'\bohg\b',

    # 简单后缀（英/西/葡/法/德通用）
    r'\binc\.?\b', r'\bltd\.?\b', r'\bllc\.?\b', r'\bcorp\.?\b',
    r'\bcorporation\b', r'\bcompany\b', r'\bco\.?\b', r'\bgmbh\b',
    r'\bag\b', r'\bs\.?a\.?r\.?l\.?\b', r'\bs\.?a\.?\b', r'\bs\.?l\.?\b',
    r'\bn\.?v\.?\b', r'\bb\.?v\.?\b', r'\bpty\.?\b', r'\bpte\.?\b',
    r'\bse\b',
    # 其他常见
    r'\bgroup\b', r'\bholdings\b', r'\bholding\b', r'\blimited\b',
    r'\bindustries\b', r'\binternational\b',
    # 前面带逗号的（如 ", Inc."）
    r',\s*\w+',
]

# 编译所有后缀正则
_LEGAL_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _LEGAL_SUFFIXES]

# 要忽略的通用词（公司名中常见但无辨识度的词）
_STOP_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'of', 'for', 'to', 'in', 'on', 'at',
    'de', 'del', 'la', 'las', 'los', 'y', 'e', 'da', 'do', 'dos', 'das',
}


def normalize_company_name(name: str) -> str:
    """
    标准化公司名，用于去重比较

    处理步骤：
    1. 去除前后空格
    2. 转小写
    3. 去除法律实体后缀（Inc., Ltd., S.A. de C.V. 等）
    4. 去除标点符号
    5. 去除通用停用词
    6. 标准化空白字符

    Example:
        "ABC Water Treatment, Inc." → "abc water treatment"
        "Agua y Saneamiento S.A. de C.V." → "agua saneamiento"
    """
    if not name:
        return ""

    name = name.strip().lower()

    # 去除法律后缀
    for pattern in _LEGAL_PATTERNS:
        name = pattern.sub('', name)

    # 去除逗号和点号之外的标点（保留连字符）
    name = re.sub(r'[^\w\s-]', ' ', name)

    # 分词并去除停用词
    tokens = name.split()
    tokens = [t for t in tokens if t and t not in _STOP_WORDS]

    # 重新组合，标准化空白
    result = ' '.join(tokens)
    result = re.sub(r'\s+', ' ', result).strip()

    return result


def is_similar_name(name1: str, name2: str) -> bool:
    """
    判断两个公司名是否指向同一实体

    匹配条件（满足任一即视为相似）：
    1. 标准化后完全相等
    2. 一个包含另一个（长的完全包含短的）
    3. 去除通用词后共享相同的关键词
    """
    if not name1 or not name2:
        return False

    # 直接相等
    n1 = name1.strip().lower()
    n2 = name2.strip().lower()
    if n1 == n2:
        return True

    # 标准化后相等
    norm1 = normalize_company_name(name1)
    norm2 = normalize_company_name(name2)
    if norm1 == norm2:
        return True
    if not norm1 or not norm2:
        return False

    # 一个包含另一个
    if norm1 in norm2 or norm2 in norm1:
        # 长度差不超过 50% 避免过短误判
        longer, shorter = (norm1, norm2) if len(norm1) >= len(norm2) else (norm2, norm1)
        if len(shorter) / len(longer) >= 0.4:
            return True

    return False


def find_existing_customer(
    db: Session,
    domain: str,
    company_name: str,
) -> Optional[Customer]:
    """
    综合查重：通过域名或公司名查找数据库中是否已存在相似客户

    查找顺序：
    1. 精确域名匹配（最高优先级，O(1) 索引查找）
    2. 标准化公司名匹配（Token 预过滤 + 模糊比对）

    Returns:
        已存在的 Customer 对象，或 None（未找到）
    """
    if not domain and not company_name:
        return None

    # 1. 按域名查询（索引查询，极快）
    if domain:
        norm_domain = normalize_url(domain)
        if norm_domain:
            existing = db.query(Customer).filter(
                Customer.website == norm_domain
            ).first()
            if existing:
                return existing

    # 2. 按标准化公司名查询
    if company_name:
        norm_name = normalize_company_name(company_name)
        if norm_name:
            tokens = norm_name.split()

            # 2a. Token 预过滤：用关键 token 做 SQL LIKE 查询，大幅缩小候选集
            if tokens:
                min_token = max(tokens, key=len)
                if len(min_token) >= 3:
                    candidates = db.query(Customer).filter(
                        Customer.company_name.ilike(f"%{min_token}%")
                    ).limit(50).all()
                else:
                    from sqlalchemy import or_
                    filters = [Customer.company_name.ilike(f"%{t}%") for t in tokens if len(t) >= 2]
                    if filters:
                        candidates = db.query(Customer).filter(or_(*filters)).limit(50).all()
                    else:
                        candidates = []
            else:
                candidates = []

            for c in candidates:
                if c.company_name and is_similar_name(c.company_name, company_name):
                    return c

            # 2b. 兜底：全表扫描（仅当 token 预过滤无结果时才触发）
            all_customers = db.query(Customer).all()
            for c in all_customers:
                if c.company_name and is_similar_name(c.company_name, company_name):
                    return c

    return None
