"""
搜索发现服务（V2.2 升级 | V3.2 运行时切换）
统一搜索入口，支持 SerpAPI 和 Tavily 两种搜索引擎
启动时自动检测可用的 API Key，支持运行时通过 set_search_engine() 切换
"""

import os
import asyncio
from typing import List, Dict, Optional

from app.services.country_language_map import get_language_info

# ── 搜索引擎选择（运行时可变） ──
# 模块启动时根据环境变量初始化，之后可通过 set_search_engine() 切换
_current_engine: str = "none"
_serpapi_key: str = os.environ.get("SERPAPI_API_KEY", "")
_tavily_key: str = os.environ.get("TAVILY_API_KEY", "")
_searxng_url: str = os.environ.get("SEARXNG_URL", "")


def _init_search_engine() -> str:
    """初始化搜索引擎（仅启动时调用一次）"""
    global _current_engine
    forced = os.environ.get("SEARCH_ENGINE", "").strip().lower()
    if forced in ("serpapi", "tavily", "searxng"):
        _current_engine = forced
        return _current_engine
    # 自动检测（SearXNG 优先 — 零成本，自部署）
    if _searxng_url:
        _current_engine = "searxng"
    elif _tavily_key:
        _current_engine = "tavily"
    elif _serpapi_key:
        _current_engine = "serpapi"
    else:
        _current_engine = "none"
    return _current_engine


def set_search_engine(engine: str) -> str:
    """运行时切换搜索引擎（'tavily' | 'serpapi' | 'searxng'）"""
    global _current_engine
    if engine not in ("tavily", "serpapi", "searxng"):
        return _current_engine  # 无效值，不切换
    # 检查是否已配置
    if engine == "tavily" and not _tavily_key:
        return _current_engine
    if engine == "serpapi" and not _serpapi_key:
        return _current_engine
    if engine == "searxng" and not _searxng_url:
        return _current_engine
    _current_engine = engine
    return _current_engine


def get_search_engine_info() -> dict:
    """获取搜索引擎配置状态"""
    return {
        "current": _current_engine,
        "available": {
            "tavily": bool(_tavily_key),
            "serpapi": bool(_serpapi_key),
            "searxng": bool(_searxng_url),
        },
        "default": "searxng" if _searxng_url else (
            "tavily" if _tavily_key else ("serpapi" if _serpapi_key else "none")
        ),
    }


# 启动时初始化
_init_search_engine()


# 搜索间隔
SEARCH_INTERVAL = 1.0


async def search_google(
    keyword: str,
    country: str,
    max_results: int = 50,
) -> List[Dict]:
    """
    统一搜索入口，根据当前运行时配置选择搜索引擎
    每个结果包含：title, website, snippet
    """
    engine = _current_engine
    print(f"  使用搜索引擎: {engine}")

    if engine == "tavily":
        from app.services.tavily_discovery import search_tavily
        return await search_tavily(keyword, country=country, max_results=max_results)
    elif engine == "serpapi":
        return await _search_via_serpapi(keyword, country, max_results)
    elif engine == "searxng":
        from app.services.searxng_discovery import search_searxng
        return await search_searxng(keyword, country=country, max_results=max_results)
    else:
        print("错误: 未配置任何搜索引擎。请设置 SEARXNG_URL、SERPAPI_API_KEY 或 TAVILY_API_KEY 环境变量")
        return []


# ═══════════════════════════════════════════
# SerpAPI 实现
# ═══════════════════════════════════════════

SERPAPI_URL = "https://serpapi.com/search"
RESULTS_PER_PAGE = 10


async def _search_via_serpapi(
    keyword: str,
    country: str,
    max_results: int = 50,
) -> List[Dict]:
    """通过 SerpAPI 搜索 Google"""
    if not _serpapi_key:
        print("错误: 未设置 SERPAPI_API_KEY 环境变量")
        return []

    all_websites = set()
    results_list = []

    max_pages = min((max_results + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE, 5)

    lang_info = get_language_info(country) if country else None

    if lang_info:
        country_code = lang_info["gl"]
        hl_code = lang_info["hl"]
        lr_code = lang_info["lr"]
        cr_code = lang_info["cr"]
        language = lang_info["language"]
        print(f"  多语言搜索: {country} → {language} (hl={hl_code}, lr={lr_code}, cr={cr_code}, gl={country_code})")
    else:
        country_code = ""
        hl_code = "en"
        lr_code = ""
        cr_code = ""

    search_query = keyword

    for page in range(max_pages):
        start = page * RESULTS_PER_PAGE
        results = await _fetch_serpapi(search_query, country_code, hl_code, lr_code, cr_code, start)

        if not results:
            print(f"  SerpAPI 第{page+1}页无结果，停止翻页")
            break

        new_count = 0
        for r in results:
            website = r.get("website", "")
            if website and website not in all_websites:
                all_websites.add(website)
                results_list.append(r)
                new_count += 1

        print(f"  SerpAPI [{keyword[:25]}...] 第{page+1}页: {len(results)}条, 新增{new_count}条")

        if new_count == 0:
            break
        if page < max_pages - 1:
            await asyncio.sleep(SEARCH_INTERVAL)

    return results_list


async def _fetch_serpapi(
    query: str, country_code: str, hl_code: str = "en",
    lr_code: str = "", cr_code: str = "", start: int = 0,
) -> Optional[List[Dict]]:
    """调用 SerpAPI 接口"""
    import httpx
    from urllib.parse import urlparse

    params = {
        "api_key": _serpapi_key,
        "engine": "google",
        "q": query,
        "num": RESULTS_PER_PAGE,
        "start": start,
        "hl": hl_code,
    }
    if country_code:
        params["gl"] = country_code
    if lr_code:
        params["lr"] = lr_code
    if cr_code:
        params["cr"] = cr_code

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(SERPAPI_URL, params=params)

            if response.status_code != 200:
                print(f"  SerpAPI HTTP {response.status_code}: {query[:40]}")
                if response.status_code == 429:
                    print("  SerpAPI 速率限制，等待5秒...")
                    await asyncio.sleep(5)
                return None

            try:
                data = response.json()
            except Exception:
                text_preview = response.text[:300].replace("\n", " ")
                print(f"  SerpAPI 返回非JSON响应: {text_preview}")
                return None

            if "error" in data:
                print(f"  SerpAPI 返回错误: {data['error']}")
                return None

            search_metadata = data.get("search_metadata", {})
            if search_metadata.get("status") == "Error":
                error_msg = data.get("error", "未知错误")
                print(f"  SerpAPI 搜索失败: {error_msg}")
                return None

            return _parse_serpapi_response(data)

    except httpx.TimeoutException:
        print(f"  SerpAPI 请求超时: {query[:40]}")
        return None
    except httpx.HTTPStatusError as e:
        print(f"  SerpAPI HTTP错误 {e.response.status_code}: {query[:40]}")
        return None
    except Exception as e:
        print(f"  SerpAPI 异常 [{type(e).__name__}]: {str(e)[:200]}")
        return None


def _parse_serpapi_response(data: dict) -> List[Dict]:
    """解析 SerpAPI 返回结果"""
    from urllib.parse import urlparse
    results = []
    organic_results = data.get("organic_results", [])

    for item in organic_results:
        try:
            title = item.get("title", "").strip()
            link = item.get("link", "").strip()
            snippet = item.get("snippet", "").strip() if item.get("snippet") else ""

            if not title or not link:
                continue

            parsed = urlparse(link)
            if not parsed.netloc:
                continue

            results.append({
                "title": title,
                "website": link,
                "snippet": snippet[:300],
            })
        except Exception:
            continue

    return results
