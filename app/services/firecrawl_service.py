"""
Firecrawl 集成服务（V3.2.6 优化 — 仅 scrape，不 crawl）
=====================================================
封装 Firecrawl SDK（AsyncFirecrawlApp）的 Scrape API 调用，
作为免费爬虫的降级方案。始终使用 1 credit 单页抓取。

使用方式:
    service = FirecrawlService()
    if service.available:
        text = await service.scrape_url("https://example.com")

没有 FIRECRAWL_API_KEY 时 available=False，不影响现有流程。
"""
import logging
from typing import Optional

logger = logging.getLogger("firecrawl_service")


class FirecrawlService:
    """Firecrawl 抓取服务（懒加载、无依赖强要求）

    所有方法均可安全调用：无 API key 或 SDK 未安装时返回 None。
    """

    def __init__(self):
        import os

        self.api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
        self.available = bool(self.api_key)
        self._app = None

        if self.available:
            logger.info(
                "Firecrawl 已配置 (key=%s...%s)",
                self.api_key[:6],
                self.api_key[-4:],
            )
        else:
            logger.debug("FIRECRAWL_API_KEY 未设置，Firecrawl 降级不可用")

    # ------------------------------------------------------------------
    # 内部：延迟初始化 SDK
    # ------------------------------------------------------------------

    async def _get_app(self):
        """延迟初始化 AsyncFirecrawlApp，避免 import 失败影响主流程"""
        if self._app is not None:
            return self._app
        if not self.available:
            return None

        try:
            from firecrawl import AsyncFirecrawlApp

            self._app = AsyncFirecrawlApp(api_key=self.api_key)
            logger.info("AsyncFirecrawlApp 初始化成功")
            return self._app
        except ImportError:
            logger.warning(
                "firecrawl-py 未安装，Firecrawl 降级不可用。"
                "请执行: pip install firecrawl-py"
            )
            self.available = False
            return None
        except Exception as e:
            logger.error("AsyncFirecrawlApp 初始化失败: %s", e)
            self.available = False
            return None

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    async def scrape_url(self, url: str) -> Optional[str]:
        """单页抓取（仅 1 credit）

        使用 Firecrawl Scrape API 抓取单页内容，返回 markdown 文本。
        适合首页抓取降级：免费爬虫连首页都拿不到时，用此方法兜底。

        Args:
            url: 目标页面 URL（须完整，含 scheme）

        Returns:
            markdown 纯文本，失败返回 None
        """
        app = await self._get_app()
        if not app:
            return None

        try:
            response = await app.scrape(url, formats=["markdown"])

            if response and response.success and response.data:
                md = response.data.markdown
                if md and isinstance(md, str) and len(md.strip()) > 20:
                    return md.strip()

            logger.debug("Firecrawl scrape 无有效内容: %s", url)
            return None

        except Exception as e:
            logger.error("Firecrawl scrape 失败 [%s]: %s", url, e)
            return None
