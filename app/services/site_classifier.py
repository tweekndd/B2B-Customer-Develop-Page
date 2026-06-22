"""
站点分类器（V2.3 新增）
功能：
1. 域名类型分类：corporate / academic / government / storage-cdn / portal-cms
2. 语言路径字典：根据国家/语言配置优先抓取的页面路径
3. 停止无效路径爆破策略：301 重定向率 > 70% 时停止抓取
"""
import re
from typing import List, Optional, Set
from urllib.parse import urlparse


# ═══════════════════════════════════════════
# 1. 域名类型分类器
# ═══════════════════════════════════════════

# 学术/教育域名关键词
ACADEMIC_KEYWORDS = {
    "university", "universidad", "universidade", "universitate",
    "universitas", "college", "facultad", "faculdade", "instituto",
    "institut", "school", "campus", "academy", "academia",
    "research", "laboratory", "lab", "edu", "ac.",
}

# 政府域名关键词
GOVERNMENT_KEYWORDS = {
    "gov", "gob", "government", "gobierno", "governo",
    "state", "municipal", "municipio", "prefeitura",
    "ministry", "ministerio", "departamento", "department",
    "parliament", "congreso", "senado", "camera",
}

# 存储/CDN 域名关键词
STORAGE_CDN_KEYWORDS = {
    "cdn", "static", "assets", "storage", "s3", "cloudfront",
    "cloudflare", "akamai", "fastly", "keycdn", "stackpath",
    "bootstrapcdn", "jsdelivr", "unpkg", "fontawesome",
}

# Portal/CMS 常见特征
PORTAL_CMS_INDICATORS = {
    "wordpress", "wp-", "wp-content", "wp-admin", "wp-includes",
    "joomla", "drupal", "magento", "shopify", "squarespace",
    "wix", "weebly", "blogger", "blogspot", "tumblr",
    "ghost", "medium", "hatenablog", "over-blog",
}


def classify_domain(domain: str) -> str:
    """
    分类域名类型
    返回: corporate / academic / government / storage-cdn / portal-cms
    """
    domain_lower = domain.lower()
    domain_parts = domain_lower.split(".")

    # 1. 学术/教育
    # 检查 .edu / .ac.xx 等
    if domain_lower.endswith(".edu") or re.search(r'\.ac\.[a-z]{2,}$', domain_lower):
        return "academic"
    for part in domain_parts:
        if part in {"edu", "ac"}:
            return "academic"
    for kw in ACADEMIC_KEYWORDS:
        if kw in domain_lower:
            # university/college 等关键词出现在域名中的很可能是学校
            if kw in {"university", "universidad", "college", "school", "campus", "academy", "instituto", "institut"}:
                return "academic"

    # 2. 政府
    if domain_lower.endswith(".gov") or re.search(r'\.gov\.[a-z]{2,}$', domain_lower):
        return "government"
    if domain_lower.endswith(".gob") or re.search(r'\.gob\.[a-z]{2,}$', domain_lower):
        return "government"
    if domain_lower.endswith(".govt"):
        return "government"
    for kw in GOVERNMENT_KEYWORDS:
        if kw in domain_parts:
            return "government"

    # 3. 存储/CDN
    for kw in STORAGE_CDN_KEYWORDS:
        if kw in domain_lower:
            return "storage-cdn"

    # 4. Portal/CMS（域名特征）
    # 某些 CMS 平台域名后缀
    if domain_lower.endswith(".blogspot.com") or domain_lower.endswith(".wordpress.com"):
        return "portal-cms"
    if domain_lower.endswith(".squarespace.com") or domain_lower.endswith(".wixsite.com"):
        return "portal-cms"
    if domain_lower.endswith(".shopify.com") or domain_lower.endswith(".myshopify.com"):
        return "portal-cms"
    if domain_lower.endswith(".weebly.com") or domain_lower.endswith(".hatenablog.com"):
        return "portal-cms"

    # 默认视为企业官网
    return "corporate"


def is_corporate_site(domain: str) -> bool:
    """判断是否为企业官网（非学术/政府/存储/Portal）"""
    site_type = classify_domain(domain)
    return site_type == "corporate"


# ═══════════════════════════════════════════
# 2. 语言路径字典
# ═══════════════════════════════════════════

# 不同语言的常见路径映射
LANGUAGE_PATHS = {
    "en": [
        "/about", "/about-us", "/company", "/services", "/projects",
        "/contact", "/products", "/solutions", "/case-studies",
        "/references", "/portfolio", "/team", "/careers",
        "/news", "/blog", "/faq", "/", "",
    ],
    "es": [
        "/nosotros", "/sobre-nosotros", "/empresa", "/servicios",
        "/proyectos", "/contacto", "/productos", "/soluciones",
        "/casos-de-exito", "/referencias", "/portafolio",
        "/equipo", "/trabaja-con-nosotros", "/noticias",
        "/blog", "/preguntas-frecuentes", "/", "",
    ],
    "pt": [
        "/sobre", "/sobre-nos", "/empresa", "/servicos",
        "/projetos", "/contato", "/produtos", "/solucoes",
        "/casos-de-sucesso", "/referencias", "/portfolio",
        "/equipe", "/trabalhe-conosco", "/noticias",
        "/blog", "/perguntas-frequentes", "/", "",
    ],
}

# 默认路径（英文兜底）
DEFAULT_PATHS = LANGUAGE_PATHS["en"]


def get_language_paths(language: str) -> List[str]:
    """
    根据语言代码获取优先抓取的路径列表
    语言代码: en / es / pt 等
    """
    lang_key = language.lower()[:2]
    paths = LANGUAGE_PATHS.get(lang_key)
    if paths:
        return paths
    return DEFAULT_PATHS


def build_priority_paths(domain: str, language: str = "en") -> List[str]:
    """
    构建优先抓取的 URL 列表
    根据目标语言使用对应的路径字典
    """
    paths = get_language_paths(language)
    base = f"https://{domain}"
    urls = [base + path for path in paths]
    return urls


# ═══════════════════════════════════════════
# 3. 停止无效路径爆破策略
# ═══════════════════════════════════════════

class RedirectTracker:
    """
    跟踪路径抓取过程中的重定向状态
    如果 301 重定向率 > 70%，则判定该站点无需继续抓取
    """

    def __init__(self):
        self.total_requests = 0
        self.redirect_count = 0
        # 记录已经跳转过的目标，避免反复跟踪同一跳转链
        self.seen_redirect_targets: Set[str] = set()

    def record_response(self, status_code: int, final_url: str, original_url: str):
        """
        记录一次请求结果
        status_code: HTTP 状态码
        final_url: 最终到达的 URL
        original_url: 原始请求的 URL
        """
        self.total_requests += 1
        # 301/302/307/308 永久/临时重定向
        if status_code in (301, 302, 307, 308):
            self.redirect_count += 1
        # 即使状态码不是 3xx，但最终 URL 和原始 URL 不同也算重定向
        elif final_url != original_url:
            self.redirect_count += 1

    @property
    def redirect_rate(self) -> float:
        """计算重定向率"""
        if self.total_requests == 0:
            return 0.0
        return self.redirect_count / self.total_requests

    @property
    def should_stop(self) -> bool:
        """
        判断是否应该停止抓取
        当总请求数 >= 3 且重定向率 > 70% 时停止
        """
        return self.total_requests >= 3 and self.redirect_rate > 0.7

    def reset(self):
        """重置跟踪器"""
        self.total_requests = 0
        self.redirect_count = 0
        self.seen_redirect_targets.clear()
