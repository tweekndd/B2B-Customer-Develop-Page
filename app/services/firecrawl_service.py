"""
Firecrawl 集成服务（V3.3 新增）
=================================
封装 Firecrawl SDK（AsyncFirecrawlApp），作为免费爬虫的降级方案。
仅使用 markdown 格式（1 credit/页），最大性价比。

使用方式:
    service = FirecrawlService()
    if service.available:
        text = await service.scrape_url("https://example.com")
        text = await service.crawl_website("https://example.com", max_pages=10)

没有 FIRECRAWL_API_KEY 时 available=False，不影响现有流程。
"""
import logging
from typing import Optional, List

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
        """单页抓取（1 credit）

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

    async def crawl_website(
        self, url: str, max_pages: int = 10, timeout_minutes: int = 5
    ) -> Optional[str]:
        """全站爬取（N credits，1 credit/页）

        使用 Firecrawl Crawl API 递归发现并抓取页面，自动处理
        sitemap、JS 渲染和反爬机制，返回合并后的 markdown。

        Args:
            url: 目标网站 URL
            max_pages: 最大抓取页数（默认 10，控制 credit 消耗）
            timeout_minutes: 爬取超时分钟数（默认 5）

        Returns:
            合并后的多页 markdown 文本（''===== 下一页 ====='' 分隔）
            失败返回 None
        """
        app = await self._get_app()
        if not app:
            return None

        try:
            job = await app.crawl(
                url=url,
                limit=max_pages,
                formats=["markdown"],
                timeout=timeout_minutes * 60,  # SDK 单位：秒
            )

            if not job or not job.data:
                logger.debug("Firecrawl crawl 无数据: %s", url)
                return None

            texts: List[str] = []
            for doc in job.data:
                md = doc.markdown if hasattr(doc, "markdown") else None
                if md and isinstance(md, str) and len(md.strip()) > 50:
                    texts.append(md.strip())

            if not texts:
                logger.debug("Firecrawl crawl 无有效文本: %s", url)
                return None

            logger.info(
                "Firecrawl crawl 成功: %s (%d 页, %d 字符)",
                url,
                len(texts),
                sum(len(t) for t in texts),
            )
            return "\n\n===== 下一页 =====\n\n".join(texts)

        except Exception as e:
            logger.error("Firecrawl crawl 失败 [%s]: %s", url, e)
            return None
