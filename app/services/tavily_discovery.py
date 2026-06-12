"""
Tavily 搜索发现服务（V2.2 新增）
通过 Tavily API 调用网络搜索
API Key 通过环境变量 TAVILY_API_KEY 传入
"""
import os
import asyncio
from typing import List, Dict, Optional
from urllib.parse import urlparse

import httpx


# Tavily API 配置
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
TAVILY_API_URL = "https://api.tavily.com/search"

# 搜索间隔（秒）
SEARCH_INTERVAL = 1.0


async def search_tavily(
    keyword: str,
    country: str = "",
    max_results: int = 50,
) -> List[Dict]:
    """
    通过 Tavily API 搜索，返回搜索结果列表
    每个结果包含：title, website, snippet
    Tavily 每次最多返回 20 条结果（免费版）
    """
    if not TAVILY_API_KEY:
        print("错误: 未设置 TAVILY_API_KEY 环境变量，无法使用 Tavily 搜索")
        return []

    all_websites = set()
    results_list = []

    # Tavily 的 search_depth 控制结果数量：basic=5, advanced=10+
    # 免费版每次最多约 20 条，通过多次调用累计
    calls_needed = (max_results + 19) // 20
    calls_needed = min(calls_needed, 3)  # 最多调 3 次（约 60 条）

    # 如果指定了国家，在关键词后拼接国家名以增强相关性
    search_query = f"{keyword} {country}" if country else keyword

    for call_idx in range(calls_needed):
        results = await _fetch_via_tavily(search_query, call_idx)

        if not results:
            print(f"  Tavily 第{call_idx+1}次无结果，停止")
            break

        # 去重
        new_count = 0
        for r in results:
            website = r.get("website", "")
            if website and website not in all_websites:
                all_websites.add(website)
                results_list.append(r)
                new_count += 1

        print(f"  Tavily [{keyword[:25]}...] 第{call_idx+1}次: {len(results)}条, 新增{new_count}条")

        if new_count == 0:
            break

        if call_idx < calls_needed - 1:
            await asyncio.sleep(SEARCH_INTERVAL)

    return results_list


async def _fetch_via_tavily(
    query: str,
    offset: int = 0,
) -> Optional[List[Dict]]:
    """
    调用 Tavily API 搜索
    API 文档: https://docs.tavily.com
    """
    payload = {
        "query": query,
        "search_depth": "advanced" if offset > 0 else "basic",
        "max_results": 20,
        "include_domains": [],
        "exclude_domains": [],
    }

    headers = {
        "Authorization": f"Bearer {TAVILY_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(TAVILY_API_URL, json=payload, headers=headers)

            if response.status_code != 200:
                print(f"  Tavily HTTP {response.status_code}: {query[:40]}")
                return None

            try:
                data = response.json()
            except Exception:
                text_preview = response.text[:300].replace("\n", " ")
                print(f"  Tavily 返回非JSON响应: {text_preview}")
                return None

            # 检查错误
            if "error" in data:
                print(f"  Tavily 返回错误: {data['error']}")
                return None

            return _parse_tavily_response(data)

    except httpx.TimeoutException:
        print(f"  Tavily 请求超时: {query[:40]}")
        return None
    except httpx.HTTPStatusError as e:
        print(f"  Tavily HTTP错误 {e.response.status_code}: {query[:40]}")
        return None
    except Exception as e:
        print(f"  Tavily 异常 [{type(e).__name__}]: {str(e)[:200]}")
        return None


def _parse_tavily_response(data: dict) -> List[Dict]:
    """
    解析 Tavily API 返回的 JSON 数据
    Tavily 返回格式: { "results": [ { "title": ..., "url": ..., "content": ... } ] }
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
