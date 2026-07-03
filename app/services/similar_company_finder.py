"""
相似客户扩展服务（V2.5 新增）
基于公司网址的相似客户扩展模块（V1简化版）

流程：
1. 抓取目标公司官网
2. LLM提取业务信息（行业、产品、关键词）
3. 在目标国家搜索相似公司
4. 规则相似度评分
5. 输出 Top N 结果
"""
import json
import asyncio
import re
import os
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse

import httpx

from app.services.website_scraper import scrape_website
from app.services.company_filter import filter_search_results, is_blacklisted
from app.services.url_normalizer import normalize_url
from app.services.keyword_analyzer import analyze_keywords
from app.services.country_language_map import get_language_info

# SSL 验证开关（与 website_scraper 共享同一环境变量）
_VERIFY_SSL = os.environ.get("SCRAPE_VERIFY_SSL", "").lower() == "true"

# ── 行业分类映射 ──
INDUSTRY_KEYWORDS = {
    "水处理设备": ["water treatment", "wastewater", "sewage", "filtration", "purification",
                  "desalination", "reverse osmosis", "RO", "ultrafiltration", " membrane"],
    "包装机械": ["packaging machine", "packaging equipment", "filling machine",
                "sealing machine", "wrapping machine", "packaging line"],
    "光伏设备": ["solar panel", "photovoltaic", "solar energy", "PV module",
                "solar inverter", "solar system", "renewable energy"],
    "建筑机械": ["construction machinery", "construction equipment", "excavator",
                "bulldozer", "crane", "concrete mixer", "heavy equipment"],
    "食品机械": ["food processing", "food machinery", "food equipment",
                "food packaging", "processing line", "food industry"],
    "化工设备": ["chemical equipment", "chemical processing", "chemical plant",
                "industrial equipment", "manufacturing equipment", "process equipment"],
    "电子/电气": ["electronic", "electrical", "electric", "electronics manufacturing",
                "PCB", "circuit board", "component", "semiconductor"],
    "汽车零部件": ["auto parts", "automotive", "car parts", "automobile",
                  "vehicle parts", "auto component", "spare parts"],
    "钢铁/金属": ["steel", "metal", "iron", "aluminum", "stainless steel",
                "metal fabrication", "metal processing", "foundry"],
    "纺织/服装": ["textile", "garment", "apparel", "fabric", "clothing",
                "knitting", "weaving", "textile machinery"],
}


async def _translate_to_local_language(
    business_info: Dict,
    target_country: str,
) -> Optional[Dict]:
    """
    将种子公司的业务信息翻译为目标国家的本地语言
    用于在非英语国家进行本地化搜索，提高相似客户发现的精准度

    Returns: 包含翻译后的 industry / products / keywords 的字典，或 None（英语国家或翻译失败）
    """
    lang_info = get_language_info(target_country)
    if not lang_info or lang_info["language"] == "English":
        return None  # 英语国家不需要翻译

    language_name = lang_info["language"]
    industry = business_info.get("industry", "")
    products = business_info.get("products", [])
    keywords = business_info.get("keywords", [])

    glm_key = os.environ.get("GLM_API_KEY", "")
    glm_url = os.environ.get(
        "GLM_API_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    )
    glm_model = os.environ.get("GLM_MODEL", "glm-4.7-flash")

    # 向后兼容：如果未设置 GLM_API_KEY，尝试读取旧的 DEEPSEEK_API_KEY
    if not glm_key:
        glm_key = os.environ.get("DEEPSEEK_API_KEY", "")

    prompt = f"""你是一个专业的B2B外贸翻译专家。请将以下与公司业务相关的英文内容翻译成{language_name}。

这些翻译将用于在{target_country}的Google搜索相似公司，所以翻译必须使用{target_country}本地企业在其官网和业务描述中常用的自然表达方式，而不是直译。

英文行业/领域（Industry）：
{industry}

英文主要产品（Products）：
{json.dumps(products, ensure_ascii=False)}

英文核心关键词（Keywords）：
{json.dumps(keywords, ensure_ascii=False)}

要求：
1. 行业和关键词必须用{language_name}准确翻译
2. 每个产品名翻译成{target_country}本地市场的惯用说法
3. 保留原始英文内容不变（JSON中的原字段）
4. 返回JSON格式

返回格式：
{{
    "industry": "翻译后的行业描述",
    "products": ["翻译后的产品1", "翻译后的产品2"],
    "keywords": ["翻译后的关键词1", "翻译后的关键词2"]
}}

只返回JSON，不要包含其他文字。"""

    payload = {
        "model": glm_model,
        "messages": [
            {"role": "system", "content": f"你是一个专业的B2B外贸翻译专家，精通{language_name}和行业术语。只返回JSON格式数据。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    headers = {
        "Authorization": f"Bearer {glm_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(glm_url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # 清理可能的代码块标记
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.strip().startswith("```"):
                        in_block = not in_block
                        continue
                    if in_block:
                        json_lines.append(line)
                if json_lines:
                    content = "\n".join(json_lines)

            translated = json.loads(content)
            print(f"  关键词已翻译为{language_name}: {translated.get('keywords', [])[:3]}...")
            return translated
    except httpx.TimeoutException:
        print(f"  本地化翻译超时（GLM API响应慢），继续使用英文搜索")
        return None
    except Exception as e:
        print(f"  本地化翻译失败，继续使用英文搜索: {str(e)[:100]}")
        return None


def _classify_industry(products: List[str], keywords: List[str]) -> str:
    """将产品/关键词映射到标准行业标签"""
    all_text = " ".join(products + keywords).lower()
    best_match = "其他"
    max_score = 0

    for industry, kw_list in INDUSTRY_KEYWORDS.items():
        score = 0
        for kw in kw_list:
            if kw in all_text:
                score += 1
        if score > max_score:
            max_score = score
            best_match = industry

    return best_match


async def extract_business_info(company_url: str) -> Optional[Dict]:
    """
    Step 1+2: 抓取网页 + LLM提取业务信息
    返回种子公司的行业、产品、关键词
    """
    # 抓取网页
    website_text = await scrape_website(company_url)
    if not website_text:
        # 尝试简化抓取
        try:
            async with httpx.AsyncClient(timeout=15, verify=_VERIFY_SSL) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
                    "Accept": "text/html",
                }
                resp = await client.get(company_url, headers=headers, follow_redirects=True)
                if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style", "noscript"]):
                        tag.decompose()
                    texts = []
                    for tag in soup.find_all(["h1", "h2", "h3", "p", "li"]):
                        t = tag.get_text(strip=True)
                        if len(t) > 10:
                            texts.append(t)
                    website_text = "\n".join(texts[:100])
        except Exception:
            pass

    if not website_text:
        return None

    # 提取关键词分析
    pos_hits, _ = analyze_keywords(website_text)
    extracted_keywords = list(pos_hits.keys()) if pos_hits else []

    # 取前3000字符交给 LLM 分析
    content_for_llm = website_text[:3000]

    # 调用 GLM 提取业务信息
    glm_key_2 = os.environ.get("GLM_API_KEY", "")
    glm_url_2 = os.environ.get(
        "GLM_API_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    )
    glm_model_2 = os.environ.get("GLM_MODEL", "glm-4.7-flash")

    # 向后兼容：如果未设置 GLM_API_KEY，尝试读取旧的 DEEPSEEK_API_KEY
    if not glm_key_2:
        glm_key_2 = os.environ.get("DEEPSEEK_API_KEY", "")

    prompt = f"""分析以下公司网页内容，提取业务信息。返回严格的JSON格式（不要包含其他文字）：

网页内容：
{content_for_llm}

请返回JSON，格式如下：
{{
    "industry": "主营行业（英文，如 Water Treatment Equipment, Packaging Machinery, Solar Energy 等）",
    "products": ["产品1", "产品2", "产品3"],
    "keywords": ["核心关键词1", "核心关键词2", "核心关键词3", "核心关键词4", "核心关键词5"],
    "company_name": "公司名称（如果能从页面中识别出来）"
}}

只返回JSON，不要包含其他文字。"""

    payload = {
        "model": glm_model_2,
        "messages": [
            {"role": "system", "content": "你是一个专业的B2B客户分析专家。根据公司网站内容提取业务信息。只返回JSON格式数据。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    headers = {
        "Authorization": f"Bearer {glm_key_2}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(glm_url_2, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # 解析JSON
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.strip().startswith("```"):
                        in_block = not in_block
                        continue
                    if in_block:
                        json_lines.append(line)
                if json_lines:
                    content = "\n".join(json_lines)

            data = json.loads(content)
            data["keywords"] = list(set(data.get("keywords", []) + extracted_keywords))
            # 行业分类
            industry = data.get("industry", "")
            if industry:
                mapped = _classify_industry(data.get("products", []), data.get("keywords", []))
                data["industry_category"] = mapped
            return data

    except json.JSONDecodeError:
        # 尝试从文本中提取JSON
        try:
            start = content.index("{")
            end = content.rindex("}") + 1
            data = json.loads(content[start:end])
            return data
        except Exception:
            # LLM失败，用关键词分析结果兜底
            if extracted_keywords:
                mapped = _classify_industry([], extracted_keywords)
                return {
                    "industry": mapped,
                    "products": [],
                    "keywords": extracted_keywords[:10],
                    "company_name": "",
                    "industry_category": mapped,
                }
            return None
    except Exception as e:
        print(f"LLM业务信息提取失败: {str(e)[:100]}")
        if extracted_keywords:
            mapped = _classify_industry([], extracted_keywords)
            return {
                "industry": mapped,
                "products": [],
                "keywords": extracted_keywords[:10],
                "company_name": "",
                "industry_category": mapped,
            }
        return None


async def search_similar_companies(
    business_info: Dict,
    target_country: str,
    max_results: int = 50,
) -> List[Dict]:
    """
    Step 4: 在目标国家搜索相似公司
    支持多语言搜索：非英语国家自动使用本地语言搜索，提高精准度
    """
    from app.services.google_discovery import search_google

    keywords = business_info.get("keywords", [])
    industry = business_info.get("industry", "")
    products = business_info.get("products", [])

    # ── 多语言翻译：非英语国家将关键词翻译为本地语言 ──
    local_info = await _translate_to_local_language(business_info, target_country)
    has_translation = local_info is not None

    # 构建搜索查询列表（用双语查询）
    search_queries: List[Tuple[str, str]] = []  # (query, language_tag)

    # ── 英文查询 ──
    if industry:
        search_queries.append((f"{industry} {target_country}", "en"))
    for product in products[:3]:
        search_queries.append((f"{product} {target_country}", "en"))
    for kw in keywords[:5]:
        search_queries.append((f"{kw} {target_country} company", "en"))

    # ── 本地语言查询（非英语国家） ──
    if has_translation:
        local_industry = local_info.get("industry", "")
        local_products = local_info.get("products", [])
        local_keywords = local_info.get("keywords", [])

        if local_industry:
            search_queries.append((local_industry, "local"))
        for product in local_products[:3]:
            search_queries.append((product, "local"))
        for kw in local_keywords[:5]:
            search_queries.append((kw, "local"))

    # 查询去重
    seen_queries = set()
    unique_queries = []
    for q, lang in search_queries:
        q_clean = q.lower().strip()
        if q_clean not in seen_queries:
            seen_queries.add(q_clean)
            unique_queries.append((q, lang))

    lang_hint = f"（含{get_language_info(target_country)['language']}本地语言搜索）" if has_translation else ""
    print(f"  相似客户搜索: {len(unique_queries)} 个搜索查询 {lang_hint}")

    # 并发搜索
    all_results = []
    seen_domains = set()

    async def search_single(query: str):
        try:
            results = await search_google(
                keyword=query,
                country=target_country,
                max_results=20,
            )
            return results or []
        except Exception as e:
            print(f"  搜索失败 [{query[:30]}]: {str(e)[:60]}")
            return []

    tasks = [search_single(q) for q, _ in unique_queries]
    search_results_list = await asyncio.gather(*tasks)

    for results in search_results_list:
        for r in results:
            website = r.get("website", "")
            if not website:
                continue
            domain = normalize_url(website)
            if domain in seen_domains:
                continue
            seen_domains.add(domain)

            # 过滤黑名单
            if is_blacklisted(website):
                continue

            all_results.append({
                "name": r.get("title", ""),
                "website": domain,
                "country": target_country,
                "snippet": r.get("snippet", ""),
            })

    print(f"  搜索汇总: {len(all_results)} 个不重复结果{'（含本地语言搜索结果）' if has_translation else ''}")

    # 过滤已存在于数据库中的客户（避免推荐已有客户）
    if all_results:
        from app.database import SessionLocal, Customer
        from app.services.deduplication import normalize_company_name

        try:
            db = SessionLocal()
            existing_domains = {
                c.website for c in db.query(Customer.website).filter(
                    Customer.website.isnot(None), Customer.website != ""
                ).all()
            }
            # 额外匹配公司名
            existing_names = {}
            for c in db.query(Customer.company_name).filter(
                Customer.company_name.isnot(None), Customer.company_name != ""
            ).all():
                norm = normalize_company_name(c[0])
                if norm:
                    existing_names[norm] = True

            before = len(all_results)
            filtered = []
            for r in all_results:
                domain = r.get("website", "")
                name = r.get("name", "")
                if domain in existing_domains:
                    continue
                norm_name = normalize_company_name(name)
                if norm_name and norm_name in existing_names:
                    continue
                filtered.append(r)

            all_results = filtered
            db.close()
            if before != len(all_results):
                print(f"  数据库去重: 排除了 {before - len(all_results)} 个已存在的客户")
        except Exception as e:
            print(f"  数据库去重跳过（不影响搜索结果）: {e}")

    return all_results


def calculate_similarity(
    candidate: Dict,
    seed_keywords: List[str],
    seed_industry: str,
) -> float:
    """
    Step 5: 规则相似度计算
    score = 0.6 * keyword_match + 0.3 * industry_match + 0.1 * content_similarity
    """
    snippet = (candidate.get("snippet") or "").lower()
    name = (candidate.get("name") or "").lower()
    combined_text = f"{name} {snippet}"

    # 关键词匹配（60%）
    keyword_hits = 0
    for kw in seed_keywords:
        if kw.lower() in combined_text:
            keyword_hits += 1
    keyword_match = min(keyword_hits / max(len(seed_keywords), 1), 1.0)

    # 行业一致性（30%）— 检测行业词是否出现在文本中
    industry_terms = seed_industry.lower().split()
    industry_hits = 0
    for term in industry_terms:
        if term in combined_text:
            industry_hits += 1
    industry_match = min(industry_hits / max(len(industry_terms), 1), 1.0)

    # 内容相似度（10%）— 简单检测是否有产品/服务类词汇
    service_indicators = ["company", "service", "product", "supplier", "manufacturer",
                         "solution", "provider", "contractor", "engineering", "industrial"]
    content_hits = sum(1 for w in service_indicators if w in combined_text)
    content_similarity = min(content_hits / len(service_indicators), 1.0)

    score = 0.6 * keyword_match + 0.3 * industry_match + 0.1 * content_similarity
    return round(score * 100, 1)  # 返回0-100分


async def find_similar_companies(
    company_url: str,
    target_country: str,
    top_n: int = 50,
) -> Dict:
    """
    主入口：基于公司网址寻找相似客户
    返回完整的结果字典
    """
    print(f"开始相似客户扩展: {company_url} → {target_country}")

    # Step 1+2: 抓取 + LLM提取
    business_info = await extract_business_info(company_url)
    if not business_info:
        return {
            "seed_company": {"name": "", "industry": "", "keywords": []},
            "similar_companies": [],
            "error": "无法从目标网址提取业务信息",
        }

    seed_company = {
        "name": business_info.get("company_name", ""),
        "industry": business_info.get("industry", ""),
        "industry_category": business_info.get("industry_category", "其他"),
        "keywords": business_info.get("keywords", []),
        "products": business_info.get("products", []),
    }

    print(f"  种子公司: {seed_company['name'] or '未知'} | 行业: {seed_company['industry']}")
    print(f"  关键词: {seed_company['keywords'][:5]}")

    # Step 4: 搜索相似公司
    candidates = await search_similar_companies(
        business_info, target_country, max_results=50
    )

    if not candidates:
        return {
            "seed_company": seed_company,
            "similar_companies": [],
            "error": "未搜索到相似公司",
        }

    # Step 5: 相似度计算
    seed_keywords = business_info.get("keywords", [])
    seed_industry = business_info.get("industry", "")

    for c in candidates:
        c["similarity_score"] = calculate_similarity(c, seed_keywords, seed_industry)

    # 按相似度排序
    candidates.sort(key=lambda x: x["similarity_score"], reverse=True)

    # 取 Top N
    top_companies = candidates[:top_n]

    # 整理输出
    similar_companies = []
    for c in top_companies:
        similar_companies.append({
            "name": c["name"],
            "website": c["website"],
            "country": c["country"],
            "similarity_score": c["similarity_score"],
        })

    print(f"  结果: 找到 {len(similar_companies)} 个相似公司")

    return {
        "seed_company": seed_company,
        "similar_companies": similar_companies,
        "total_found": len(candidates),
        "error": None,
    }
