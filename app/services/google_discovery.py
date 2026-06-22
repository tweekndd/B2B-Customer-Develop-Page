"""
搜索发现服务（V2.2 升级）
统一搜索入口，支持 SerpAPI 和 Tavily 两种搜索引擎
通过环境变量 SEARCH_ENGINE 切换：serpapi / tavily
如果未设置 SEARCH_ENGINE，自动根据已配置的 API Key 决定
"""

import os
import asyncio
from typing import List, Dict, Optional

from app.services.country_language_map import get_language_info

# ── 搜索引擎选择 ──
# 优先级: SEARCH_ENGINE 环境变量 > 自动检测
_SEARCH_ENGINE = os.environ.get("SEARCH_ENGINE", "").strip().lower()


def _detect_search_engine() -> str:
    """自动检测可用的搜索引擎"""
    if _SEARCH_ENGINE in ("serpapi", "tavily"):
        return _SEARCH_ENGINE

    serpapi_key = os.environ.get("SERPAPI_API_KEY", "")
    tavily_key = os.environ.get("TAVILY_API_KEY", "")

    if _SEARCH_ENGINE == "tavily":
        return "tavily"
    if _SEARCH_ENGINE == "serpapi":
        return "serpapi"
    # 自动检测
    if tavily_key:
        return "tavily"
    if serpapi_key:
        return "serpapi"
    return "none"


# 搜索间隔
SEARCH_INTERVAL = 1.0


async def search_google(
    keyword: str,
    country: str,
    max_results: int = 50,
) -> List[Dict]:
    """
    统一搜索入口，根据配置自动选择搜索引擎
    每个结果包含：title, website, snippet
    """
    engine = _detect_search_engine()
    print(f"  使用搜索引擎: {engine}")

    if engine == "tavily":
        from app.services.tavily_discovery import search_tavily
        return await search_tavily(keyword, country=country, max_results=max_results)
    elif engine == "serpapi":
        return await _search_via_serpapi(keyword, country, max_results)
    else:
        print("错误: 未配置任何搜索引擎。请设置 SERPAPI_API_KEY 或 TAVILY_API_KEY 环境变量")
        return []


# ═══════════════════════════════════════════
# SerpAPI 实现
# ═══════════════════════════════════════════

SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY", "")
SERPAPI_URL = "https://serpapi.com/search"
RESULTS_PER_PAGE = 10


async def _search_via_serpapi(
    keyword: str,
    country: str,
    max_results: int = 50,
) -> List[Dict]:
    """通过 SerpAPI 搜索 Google"""
    if not SERPAPI_API_KEY:
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
        "api_key": SERPAPI_API_KEY,
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
