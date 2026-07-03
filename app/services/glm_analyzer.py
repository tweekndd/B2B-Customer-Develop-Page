"""
GLM AI分析服务
调用智谱 GLM API分析客户官网文本
生成客户类型、采购概率、开发切入点等分析结果
API Key 通过环境变量 GLM_API_KEY 传入
"""
import os
import json
import asyncio
from typing import Optional, Dict, Any
import httpx


# GLM API配置
GLM_API_KEY = os.environ.get("GLM_API_KEY", "")
GLM_API_URL = os.environ.get(
    "GLM_API_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions"
)
GLM_MODEL = os.environ.get("GLM_MODEL", "glm-4.7-flash")


# 向后兼容：如果未设置 GLM_API_KEY，尝试读取旧的 DEEPSEEK_API_KEY
if not GLM_API_KEY:
    GLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")


def _build_prompt(website_text: str) -> str:
    """构建发送给AI的提示词，控制在3000字符以内"""
    truncated_text = website_text[:3000]

    prompt = f"""请分析以下公司网页内容，返回严格的JSON格式（不要包含其他文字）：

网页内容：
{truncated_text}

请分析并返回JSON，格式如下：
{{
    "company_type": "公司类型（EPC / Contractor / Water Treatment Company / Manufacturer / Distributor / Consultant / End User / Other）",
    "analysis_reason": "分析原因（中文，50字以内）",
    "sales_hook": "推荐开发切入点（中文，50字以内）",
    "target_position": "推荐联系职位（中文，如CEO / Procurement Manager / Project Manager）",
    "summary": "英文客户摘要，50字以内",
    "identified_projects": "如果页面中有项目案例信息，请提取描述（中文，100字以内），没有则返回空字符串",
    "address_city": "如果网页内容中包含公司地址/城市信息，提取城市名称（英文优先，如无英文可用中文），没有则返回空字符串",
}}"""

    return prompt


async def analyze_company(website_text: str) -> Optional[Dict[str, Any]]:
    """调用GLM API分析公司，返回解析后的JSON字典（含自动重试）"""
    if not GLM_API_KEY:
        print("未设置GLM_API_KEY（或DEEPSEEK_API_KEY）环境变量，跳过AI分析")
        return None

    prompt = _build_prompt(website_text)

    payload = {
        "model": GLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是一位专业的外贸客户分析专家。请根据公司官网内容分析客户类型和采购潜力。只返回JSON格式数据。",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }

    headers = {
        "Authorization": f"Bearer {GLM_API_KEY}",
        "Content-Type": "application/json",
    }

    # 最大重试 3 次，应对免费 API 高峰期限流/超时
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    GLM_API_URL, headers=headers, json=payload
                )
                response.raise_for_status()
                result = response.json()

                ai_content = result["choices"][0]["message"]["content"]
                return _parse_ai_response(ai_content)

        except httpx.TimeoutException:
            if attempt < max_retries:
                wait = attempt * 2
                print(f"GLM API 请求超时，{wait}秒后第{attempt + 1}次重试...")
                await asyncio.sleep(wait)
            else:
                print(f"GLM API 请求超时（已重试{max_retries}次）")
                return None
        except httpx.HTTPStatusError as e:
            reason = ""
            try:
                body = e.response.json()
                reason = body.get("error", {}).get("message", "")
            except Exception:
                reason = e.response.text[:100]
            # 429/503 可重试，其他错误直接放弃
            if e.response.status_code in (429, 502, 503) and attempt < max_retries:
                wait = attempt * 3
                print(f"GLM API 限流({reason})，{wait}秒后第{attempt + 1}次重试...")
                await asyncio.sleep(wait)
            else:
                print(f"GLM API HTTP错误: {e.response.status_code} - {reason}")
                return None
        except Exception as e:
            print(f"GLM API 调用异常: {type(e).__name__}: {str(e)[:200]}")
            return None


def _parse_ai_response(content: str) -> Optional[Dict[str, Any]]:
    """解析AI返回的JSON内容，处理Markdown代码块包裹的情况"""
    content = content.strip()

    # 移除可能的Markdown代码块标记
    if content.startswith("```"):
        lines = content.split("\n")
        json_lines = []
        in_code_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                json_lines.append(line)
        if json_lines:
            content = "\n".join(json_lines)

    # 尝试解析JSON
    try:
        data = json.loads(content)
        return data
    except json.JSONDecodeError:
        try:
            start = content.index("{")
            end = content.rindex("}") + 1
            json_str = content[start:end]
            data = json.loads(json_str)
            return data
        except (ValueError, json.JSONDecodeError):
            print(f"无法解析AI返回的JSON: {content[:200]}")
            return None


def generate_summary(ai_result: Dict[str, Any], customer_info: Dict[str, str]) -> str:
    """根据AI分析结果生成150字以内的英文摘要"""
    # 优先使用AI返回的summary字段
    summary = ai_result.get("summary", "")
    if summary and len(summary) <= 150:
        return summary

    # 备用：手动拼接
    company_type = ai_result.get("company_type", "")
    country = customer_info.get("country", "")
    parts = []
    if country:
        parts.append(country)
    if company_type and company_type != "Other":
        parts.append(company_type)

    summary = " ".join(parts) if parts else "Company"
    if len(summary) > 150:
        summary = summary[:147] + "..."

    return summary
