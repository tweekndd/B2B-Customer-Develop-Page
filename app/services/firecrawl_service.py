"""
Reader by Jina AI 集成服务（V3.2.6 优化 → V4.2 迁移至 Reader）
===============================================================

替代 Firecrawl（免费额度消耗太快），使用 Jina AI Reader API
(r.jina.ai) 作为免费爬虫的降级方案。可自托管消除任何限制。

优势：
  - 完全免费（无额度限制）— https://r.jina.ai 官方称可用于生产
  - 无需 API key，零配置
  - HTTP API，零 SDK 依赖（httpx 已有）
  - JS 渲染支持（x-engine: browser）
  - 可选自托管 Docker 镜像 ghcr.io/jina-ai/reader:oss

使用方式:
    service = FirecrawlService()  # 接口不变，对外透明
    if service.available:
        text = await service.scrape_url("https://example.com")

环境变量:
  READER_BASE_URL     — 默认 https://r.jina.ai，自托管时改为 http://localhost:3000
  READER_ENGINE       — auto / browser / curl（默认 auto）
  FIRECRAWL_API_KEY   — 可选旧版 Firecrawl 兜底（不设置时仅用 Reader）
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("firecrawl_service")


class FirecrawlService:
    """Reader by Jina AI 抓取服务（懒加载、无依赖强要求）

    向后兼容：类名和方法签名不变，替换 Firecrawl SDK 为 Reader API。
    所有方法均可安全调用：网络失败时返回 None。
    """

    def __init__(self):
        self.available = True  # Reader 无需 API key，始终可用
        self._client: Optional[httpx.AsyncClient] = None

        # Reader 配置
        self.reader_base_url = (
            os.environ.get("READER_BASE_URL", "").strip() or "https://r.jina.ai"
        )
        self.reader_engine = os.environ.get("READER_ENGINE", "").strip() or "auto"

        # 可选：旧版 Firecrawl 作为最后兜底
        self.fc_api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
        self._fc_app = None

        logger.info(
            "Reader 已配置 (endpoint=%s, engine=%s)",
            self.reader_base_url,
            self.reader_engine,
        )
        if self.fc_api_key:
            logger.info(
                "Firecrawl 仍配置为最后兜底 (key=%s...%s)",
                self.fc_api_key[:6],
                self.fc_api_key[-4:],
            )

    # ------------------------------------------------------------------
    # 内部：HTTP 客户端
    # ------------------------------------------------------------------

    async def _get_client(self) -> Optional[httpx.AsyncClient]:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        return self._client

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    async def scrape_url(self, url: str) -> Optional[str]:
        """单页抓取（零成本，通过 Reader API）

        使用 Jina AI Reader (r.jina.ai) 将 URL 转为 LLM 友好的 markdown。
        支持 JS 渲染、反爬虫页面。

        Args:
            url: 目标页面 URL（须完整，含 scheme）

        Returns:
            markdown 纯文本，失败返回 None
        """
        # ---- 优先使用 Reader (r.jina.ai) ----
        result = await self._scrape_via_reader(url)
        if result:
            return result

        # ---- 兜底：旧版 Firecrawl（如有配置） ----
        if self.fc_api_key:
            logger.info("Reader 失败，尝试 Firecrawl 兜底: %s", url)
            return await self._scrape_via_firecrawl(url)

        return None

    async def _scrape_via_reader(self, url: str) -> Optional[str]:
        """通过 Jina AI Reader API 抓取"""
        client = await self._get_client()
        if not client:
            return None

        reader_url = f"{self.reader_base_url}/{url}"

        try:
            headers = {
                "Accept": "application/json",
            }
            if self.reader_engine and self.reader_engine != "auto":
                headers["X-Engine"] = self.reader_engine

            response = await client.get(reader_url, headers=headers)
            response.raise_for_status()

            # Reader 返回 JSON，data.content 是 markdown
            data = response.json()
            content = data.get("data", {}).get("content")
            if content and isinstance(content, str) and len(content.strip()) > 20:
                logger.info("Reader 抓取成功 (%d chars): %s", len(content), url)
                return content.strip()

            # JSON 无内容时，尝试纯文本响应
            text = response.text
            if text and len(text.strip()) > 20:
                return text.strip()

            logger.debug("Reader 无有效内容: %s", url)
            return None

        except httpx.HTTPStatusError as e:
            logger.warning("Reader HTTP 错误 [%s]: %s %s", url, e.response.status_code, e)
            return None
        except Exception as e:
            logger.warning("Reader 抓取失败 [%s]: %s", url, e)
            return None

    async def _scrape_via_firecrawl(self, url: str) -> Optional[str]:
        """通过旧版 Firecrawl SDK 兜底（原实现，保留向后兼容）"""
        try:
            from firecrawl import AsyncFirecrawlApp

            if self._fc_app is None:
                self._fc_app = AsyncFirecrawlApp(api_key=self.fc_api_key)

            response = await self._fc_app.scrape(url, formats=["markdown"])

            if response and response.success and response.data:
                md = response.data.markdown
                if md and isinstance(md, str) and len(md.strip()) > 20:
                    logger.info("Firecrawl 兜底抓取成功 (%d chars): %s", len(md), url)
                    return md.strip()

            logger.debug("Firecrawl 兜底无有效内容: %s", url)
            return None

        except ImportError:
            logger.warning("firecrawl-py 未安装，Firecrawl 兜底不可用")
            return None
        except Exception as e:
            logger.error("Firecrawl 兜底失败 [%s]: %s", url, e)
            return None

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
