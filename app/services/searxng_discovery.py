"""
SearXNG 搜索发现服务（V4.3 新增）
通过本地 SearXNG 实例进行网络搜索
SearXNG URL 通过环境变量 SEARXNG_URL 传入（默认 http://127.0.0.1:8888）
完全免费，无需 API Key
"""
import os
import asyncio
from typing import List, Dict, Optional
from urllib.parse import urlparse, quote

import httpx


# SearXNG 配置
SEARXNG_URL = os.environ.get("SEARXNG_URL", "").rstrip("/") or "http://127.0.0.1:8888"

# 搜索间隔（秒）
SEARCH_INTERVAL = 1.0

# SearXNG 每页结果数（不可配置，固定值）
RESULTS_PER_PAGE = 10


async def search_searxng(
    keyword: str,
    country: str = "",
    max_results: int = 50,
) -> List[Dict]:
    """
    通过 SearXNG 搜索，返回搜索结果列表
    每个结果包含：title, website, snippet
    SearXNG 每页返回约 10 条结果，通过翻页累计到 max_results
    """
    all_websites = set()
    results_list = []

    # 计算需要翻多少页（SearXNG 每页固定 ~10 条）
    max_pages = min((max_results + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE, 10)

    # 如果有国家信息，尝试映射到 SearXNG 语言代码
    language = _country_to_lang(country) if country else ""

    for page in range(1, max_pages + 1):
        results = await _fetch_via_searxng(keyword, language, page)

        if not results:
            print(f"  SearXNG 第{page}页无结果，停止翻页")
            break

        # 去重
        new_count = 0
        for r in results:
            website = r.get("website", "")
            if website and website not in all_websites:
                all_websites.add(website)
                results_list.append(r)
                new_count += 1

        print(f"  SearXNG [{keyword[:25]}...] 第{page}页: {len(results)}条, 新增{new_count}条")

        if new_count == 0:
            break

        if page < max_pages:
            await asyncio.sleep(SEARCH_INTERVAL)

    return results_list


async def _fetch_via_searxng(
    query: str,
    language: str = "",
    page: int = 1,
) -> Optional[List[Dict]]:
    """
    调用 SearXNG JSON API 搜索
    API 文档: https://docs.searxng.org/dev/search_api.html
    """
    params = {
        "q": query,
        "format": "json",
        "pageno": page,
    }
    if language:
        params["language"] = language

    # 默认启用多个引擎提高覆盖率
    params["engines"] = "duckduckgo,bing,startpage,brave"

    url = f"{SEARXNG_URL}/search"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)

            if response.status_code != 200:
                print(f"  SearXNG HTTP {response.status_code}: {query[:40]}")
                if response.status_code == 403:
                    print("  SearXNG 返回 403，可能未启用 JSON 格式。")
                    print("  请确保 settings.yml 中 search.formats 包含 json")
                return None

            try:
                data = response.json()
            except Exception:
                text_preview = response.text[:300].replace("\n", " ")
                print(f"  SearXNG 返回非JSON响应: {text_preview}")
                return None

            return _parse_searxng_response(data)

    except httpx.ConnectError:
        print(f"  SearXNG 连接失败（{SEARXNG_URL}），请确认 SearXNG 服务已启动")
        return None
    except httpx.TimeoutException:
        print(f"  SearXNG 请求超时: {query[:40]}")
        return None
    except httpx.HTTPStatusError as e:
        print(f"  SearXNG HTTP错误 {e.response.status_code}: {query[:40]}")
        return None
    except Exception as e:
        print(f"  SearXNG 异常 [{type(e).__name__}]: {str(e)[:200]}")
        return None


def _parse_searxng_response(data: dict) -> List[Dict]:
    """
    解析 SearXNG JSON API 返回的数据
    返回格式: { "results": [ { "title": ..., "url": ..., "content": ..., "engine": ... } ] }
    """
    results = []
    raw_results = data.get("results", [])

    for item in raw_results:
        try:
            title = item.get("title", "").strip()
            link = item.get("url", "").strip()
            snippet = item.get("content", "").strip() if item.get("content") else ""

            if not title or not link:
                continue

            # 验证URL是否有效
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


def _country_to_lang(country: str) -> str:
    """
    将国家名映射为 SearXNG 语言代码
    便于按目标国家搜索时获得该语言的结果
    """
    country_lang_map = {
        "germany": "de", "deutschland": "de",
        "france": "fr", "frankreich": "fr",
        "spain": "es", "spanien": "es",
        "italy": "it", "italien": "it",
        "netherlands": "nl", "niederlande": "nl",
        "poland": "pl", "polen": "pl",
        "sweden": "sv", "schweden": "sv",
        "norway": "no", "norwegen": "no",
        "denmark": "da", "dänemark": "da",
        "finland": "fi", "finnland": "fi",
        "portugal": "pt",
        "czech": "cs", "czech republic": "cs",
        "hungary": "hu", "ungarn": "hu",
        "romania": "ro", "rumänien": "ro",
        "russia": "ru", "russland": "ru",
        "japan": "ja", "japan": "ja",
        "china": "zh", "china mainland": "zh",
        "taiwan": "zh-tw",
        "hong kong": "zh-hk",
        "korea": "ko", "south korea": "ko",
        "india": "hi", "indien": "hi",
        "brazil": "pt-br", "brasilien": "pt-br",
        "turkey": "tr", "türkei": "tr",
        "uk": "en-gb", "united kingdom": "en-gb",
        "usa": "en", "united states": "en",
        "australia": "en-au",
        "canada": "en-ca",
        "switzerland": "de-ch", "switzerland": "de-ch",
        "austria": "de-at", "österreich": "de-at",
        "belgium": "nl-be",
        "singapore": "en-sg",
        "malaysia": "ms",
        "indonesia": "id",
        "thailand": "th",
        "vietnam": "vi",
        "philippines": "fil",
        "argentina": "es-ar",
        "mexico": "es-mx",
        "colombia": "es-co",
        "chile": "es-cl",
        "peru": "es-pe",
        "south africa": "en-za",
        "nigeria": "en-ng",
        "egypt": "ar-eg",
        "uae": "ar-ae",
        "saudi arabia": "ar-sa",
        "israel": "he",
    }
    key = country.strip().lower()
    return country_lang_map.get(key, "")
