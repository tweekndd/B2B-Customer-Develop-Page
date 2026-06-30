"""
官网抓取服务
异步方式访问网站，优先抓取指定页面路径的纯文本内容

URL 发现策略（V2 — 多阶段发现）:
  1. 扩展路径列表 — 覆盖 contactus, about_us, en/contact 等常见变体
  2. HEAD 预检 — 对候选路径先发 HEAD 请求，只抓取存在的页面
  3. 智能发现 — 解析首页链接，自动发现 contact/about/services 类页面
  4. 性能控制 — 限制并发数和总请求量，避免无限制增加请求
"""
import asyncio
import os
import logging
from typing import Optional, Set
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

# SSL 验证开关：设为 "true" 启用证书验证（更安全，但可能因目标网站证书问题导致抓取失败）
# 可通过环境变量 SCRAPE_VERIFY_SSL=true 开启
_VERIFY_SSL = os.environ.get("SCRAPE_VERIFY_SSL", "").lower() == "true"

logger = logging.getLogger("website_scraper")

# ============================================================
# Firecrawl 降级支持（延迟初始化，避免缺少 SDK 时导入失败）
# ============================================================
_firecrawl_instance = None


def _get_firecrawl_service():
    """懒加载 FirecrawlService 单例"""
    global _firecrawl_instance
    if _firecrawl_instance is None:
        try:
            from app.services.firecrawl_service import FirecrawlService

            _firecrawl_instance = FirecrawlService()
        except ImportError:
            logger.debug("FirecrawlService 不可用（未安装 firecrawl-py）")
            _firecrawl_instance = None
        except Exception as e:
            logger.warning("FirecrawlService 初始化异常: %s", e)
            _firecrawl_instance = None
    return _firecrawl_instance


# ============================================================
# HEAD 预检路径列表
# 爬虫先对这些路径发 HEAD 请求，只对返回 200 的发起 GET 抓取
# 覆盖了常见的连字符、下划线、无分隔符、PHP/HTML 后缀等变体
# ============================================================
PROBE_PATHS = [
    # ---- About / Company ----
    "/about",
    "/about-us",
    "/about_us",
    "/about-company",
    "/about_company",
    "/about.php",
    "/company",
    "/our-company",
    "/our_company",
    "/company/about-us",
    "/company/about",
    # ---- Services / Solutions ----
    "/services",
    "/service",
    "/our-services",
    "/our-service",
    "/our_services",
    "/services.php",
    "/solutions",
    "/what-we-do",
    "/whatwedo",
    # ---- Contact ----
    "/contact",
    "/contact-us",
    "/contact_us",
    "/contactus",
    "/contact.php",
    "/get-in-touch",
    "/getintouch",
    "/support",
    "/help",
    # ---- Projects / Portfolio ----
    "/projects",
    "/portfolio",
    "/cases",
    "/case-studies",
]

# ============================================================
# 智能发现的匹配关键词
# 用于从首页解析到的链接中筛选出目标页面
# ============================================================
_CONTACT_KEYWORDS = frozenset({
    "contact", "getintouch", "get-in-touch", "reach", "reach-us",
    "support", "help", "inquiry",
    # 中文
    "联络", "联系我们", "联系",
})

_ABOUT_KEYWORDS = frozenset({
    "about", "about-us", "about_us", "about-company", "about_company",
    "company", "our-company", "our_company", "who-we-are", "whoweare",
    "our-team", "team",
    # 中文
    "关于", "关于我们", "公司",
})

_SERVICES_KEYWORDS = frozenset({
    "service", "services", "our-services", "our-service", "our_services",
    "solutions", "what-we-do", "whatwedo", "our-work", "our_work",
    "capabilities",
    # 中文
    "产品", "服务", "案例",
})

_ALL_DISCOVERY_KEYWORDS = frozenset(
    _CONTACT_KEYWORDS | _ABOUT_KEYWORDS | _SERVICES_KEYWORDS
)

# ============================================================
# 超时与并发控制
# ============================================================
TIMEOUT_SECONDS = 15
HEAD_TIMEOUT_SECONDS = 10  # HEAD 请求无需下载 body，超时可以更短
MAX_CONCURRENT = 5
MAX_DISCOVERED_URLS = 10   # 从首页发现到的链接上限
MAX_TOTAL_GETS = 20        # 总 GET 请求上限（含首页）


def _extract_text_from_html(html: str) -> str:
    """
    从HTML中提取纯文本
    - 自动过滤HTML标签、JS、CSS
    - 保留可阅读文本
    """
    soup = BeautifulSoup(html, "html.parser")

    # 移除script和style标签
    for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
        tag.decompose()

    # 获取文本
    text = soup.get_text(separator="\n")

    # 清理多余空白
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            lines.append(line)

    # 合并成段落
    cleaned = "\n\n".join(lines)
    return cleaned


def _normalize_url(website_url: str) -> Optional[str]:
    """规范化URL，确保有scheme"""
    if not website_url:
        return None
    if not website_url.startswith(("http://", "https://")):
        website_url = "https://" + website_url
    parsed = urlparse(website_url)
    if not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _discover_relevant_links(base_url: str, html: Optional[str]) -> Set[str]:
    """
    从首页 HTML 中解析 <a> 链接，找出 contact/about/services 相关页面。

    匹配策略：
    - 检查 <a href="..."> 的路径部分是否包含关键词
    - 检查链接文本是否包含关键词（如 "Contact Us"、"About"）
    - 只保留同域名链接，排除锚点、javascript:、首页自身

    返回同域下的绝对 URL 集合。
    """
    if not html:
        return set()

    soup = BeautifulSoup(html, "html.parser")
    discovered: Set[str] = set()
    parsed_base = urlparse(base_url)
    count_found = 0

    for a_tag in soup.find_all("a", href=True):
        if count_found >= MAX_DISCOVERED_URLS * 2:  # 提前剪枝，避免全量扫描
            break

        href = a_tag["href"].strip()
        text = (a_tag.get_text(strip=True) or "").lower()
        href_lower = href.lower()

        # 排除无效链接
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue

        # 关键词匹配（href 或 link text 包含任意关键词）
        if not any(kw in href_lower or kw in text for kw in _ALL_DISCOVERY_KEYWORDS):
            continue

        # 解析为绝对 URL
        if href.startswith("/"):
            full_url = base_url + href
        elif href.startswith(("http://", "https://")):
            full_url = href
        else:
            # 相对路径，拼接处理
            full_url = base_url.rstrip("/") + "/" + href

        # 跳过外部域名
        parsed = urlparse(full_url)
        if parsed.netloc != parsed_base.netloc:
            continue

        # 去掉锚点 / fragment，保留 path
        clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        # 跳过首页
        if clean == base_url.rstrip("/") or clean == base_url + "/":
            continue

        # 跳过重复
        if clean in discovered:
            continue

        discovered.add(clean)
        count_found += 1

    return discovered


async def _fetch_single_page(
    client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore
) -> Optional[str]:
    """抓取单个页面，返回纯文本内容"""
    async with semaphore:
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            }
            response = await client.get(
                url, headers=headers, timeout=TIMEOUT_SECONDS, follow_redirects=True
            )
            response.raise_for_status()

            # 只处理HTML页面
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                return None

            return _extract_text_from_html(response.text)

        except Exception as e:
            logger.warning("GET 抓取失败: %s - %s", url, e)
            return None


async def _fetch_raw_html(
    client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore
) -> Optional[str]:
    """抓取单个页面，返回原始 HTML（用于链接发现）"""
    async with semaphore:
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
            }
            response = await client.get(
                url, headers=headers, timeout=TIMEOUT_SECONDS, follow_redirects=True
            )
            response.raise_for_status()

            # 只处理HTML页面
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                return None

            return response.text  # 返回原始 HTML

        except Exception as e:
            logger.warning("GET 原始 HTML 抓取失败: %s - %s", url, e)
            return None


async def _probe_paths(
    client: httpx.AsyncClient,
    base_url: str,
    paths: list,
    semaphore: asyncio.Semaphore,
) -> Set[str]:
    """
    对一组候选路径发送 HEAD 请求，返回状态码为 200 的路径集合。

    HEAD 请求只传输响应头，不下载 body，比 GET 轻量很多。
    共享主 semaphore，避免过度占用连接池。
    """
    valid: Set[str] = set()

    async def _head_one(path: str) -> Optional[str]:
        url = base_url + path
        async with semaphore:
            try:
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                }
                response = await client.head(
                    url,
                    headers=headers,
                    timeout=HEAD_TIMEOUT_SECONDS,
                    follow_redirects=True,
                )
                if response.status_code == 200:
                    return path
            except Exception as e:
                logger.warning("HEAD 预检失败: %s - %s", url, e)
        return None

    tasks = [_head_one(p) for p in paths]
    results = await asyncio.gather(*tasks)
    for r in results:
        if r is not None:
            valid.add(r)
    return valid


async def scrape_website(website_url: str) -> Optional[str]:
    """
    异步抓取客户官网
    采用多阶段 URL 发现策略，带 Firecrawl 自动降级：

      第1层降级：首页 GET 失败 → Firecrawl Scrape（1 credit）
      第2层降级：33条 HEAD 成功率 < 50% → Firecrawl Crawl（~10 credits）
      第3层降级：GET 后内容合计 < 200 字符 → Firecrawl Crawl（~10 credits）
      全部通过 → 免费爬虫搞定

    返回合并后的纯文本，如果全无内容则返回 None。
    """
    base_url = _normalize_url(website_url)
    if not base_url:
        return None

    # 初始化 Firecrawl（无 API key 时 available=False）
    firecrawl = _get_firecrawl_service()

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with httpx.AsyncClient(verify=_VERIFY_SSL) as client:
        # ---- 阶段 1：抓取首页 ----
        homepage_html = await _fetch_raw_html(client, base_url + "/", semaphore)

        # ===== 第1层降级：首页 GET 失败 =====
        if homepage_html is None and firecrawl and firecrawl.available:
            logger.info(
                "[降级-1/3] 首页 GET 失败 → Firecrawl Scrape: %s", base_url
            )
            fc_result = await firecrawl.scrape_url(base_url)
            if fc_result:
                return _truncate_content(fc_result)
            logger.info(
                "Firecrawl Scrape 未返回内容，继续免费流程: %s", base_url
            )

        homepage_text = _extract_text_from_html(homepage_html) if homepage_html else None

        # ---- 阶段 2：并行执行 链接发现 + HEAD 预检 ----
        async def _discover() -> Set[str]:
            if homepage_html:
                # 使用线程执行 BeautifulSoup 解析，避免阻塞事件循环
                return await asyncio.to_thread(
                    _discover_relevant_links, base_url, homepage_html
                )
            return set()

        async def _probe() -> Set[str]:
            return await _probe_paths(client, base_url, PROBE_PATHS, semaphore)

        discovered_urls, valid_paths = await asyncio.gather(_discover(), _probe())

        # ===== 第2层降级：HEAD 成功率 < 50% =====
        probe_total = len(PROBE_PATHS)
        probe_success = len(valid_paths)
        probe_rate = probe_success / probe_total if probe_total > 0 else 0
        logger.info(
            "HEAD 预检统计: %d/%d 成功 (%.1f%%) — %s",
            probe_success,
            probe_total,
            probe_rate * 100,
            base_url,
        )

        if probe_rate < 0.5 and firecrawl and firecrawl.available:
            logger.info(
                "[降级-2/3] HEAD 成功率 %.1f%% < 50%% → Firecrawl Crawl: %s",
                probe_rate * 100,
                base_url,
            )
            fc_result = await firecrawl.crawl_website(base_url)
            if fc_result:
                return _truncate_content(fc_result)
            logger.info(
                "Firecrawl Crawl 未返回内容，继续免费流程: %s", base_url
            )

        # ---- 阶段 3：构建最终 GET 目标列表 ----
        # 优先级：首页发现的链接 > HEAD 预检确认的路径
        get_targets: list[str] = []

        # 优先加入从首页发现的链接（更可能包含有价值内容）
        for url in discovered_urls:
            if len(get_targets) >= MAX_DISCOVERED_URLS:
                break
            if url not in get_targets:
                get_targets.append(url)

        # 加入 HEAD 验证通过的路径（前提是尚未在列表中且未超上限）
        for path in valid_paths:
            url = base_url + path
            if url not in get_targets and len(get_targets) < MAX_TOTAL_GETS:
                get_targets.append(url)

        # ---- 阶段 4：GET 抓取所有目标页面 ----
        fetch_tasks = [
            _fetch_single_page(client, url, semaphore) for url in get_targets
        ]
        fetched_texts = await asyncio.gather(*fetch_tasks) if get_targets else []

    # ===== 第3层降级：内容合计 < 200 字符 =====
    total_content = len(homepage_text) if homepage_text else 0
    for text in fetched_texts:
        if text:
            total_content += len(text)

    if total_content > 0 and total_content < 200 and firecrawl and firecrawl.available:
        logger.info(
            "[降级-3/3] 内容仅 %d 字符 → Firecrawl Crawl: %s",
            total_content,
            base_url,
        )
        fc_result = await firecrawl.crawl_website(base_url)
        if fc_result:
            return _truncate_content(fc_result)

    # ---- 阶段 5：合并去重 ----
    all_texts: list[str] = []
    seen = set()

    # 首页优先（首页通常包含最重要的摘要信息）
    if homepage_text and len(homepage_text) > 50:
        key = homepage_text[:100]
        seen.add(key)
        all_texts.append(homepage_text)

    # 其他页面
    for text in fetched_texts:
        if text and len(text) > 50:
            key = text[:100]
            if key not in seen:
                seen.add(key)
                all_texts.append(text)

    if not all_texts:
        # 有内容但不足 200 字符的情况已在第3层处理，到这里说明确实没内容
        return None

    # 合并所有文本
    combined = "\n\n===== 下一页 =====\n\n".join(all_texts)

    # 限制总长度
    if len(combined) > 50000:
        combined = combined[:50000]

    return combined


def _truncate_content(text: str, max_chars: int = 50000) -> str:
    """统一截断超长文本"""
    if len(text) > max_chars:
        logger.debug("内容超长，截断至 %d 字符", max_chars)
        return text[:max_chars]
    return text
