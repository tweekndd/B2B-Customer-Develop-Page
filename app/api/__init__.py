"""
API 路由聚合模块（V2.8 重构）
将单体 routes.py 拆分为 customers / discovery / sync / config 四个独立模块，
通过此文件组合为统一路由器，保持对外接口不变。
"""
from fastapi import APIRouter

# 统一的 /api 前缀路由器（main.py 通过此对象注册所有 API）
router = APIRouter(prefix="/api")

# 导入各子模块的路由器
from app.api.customers import router as _customers  # noqa: E402
from app.api.discovery import router as _discovery  # noqa: E402
from app.api.sync import router as _sync            # noqa: E402
from app.api.config import router as _config        # noqa: E402
from app.api.hunter import router as _hunter        # noqa: E402
from app.api.tomba import router as _tomba          # noqa: E402
from app.api.waterfall import router as _waterfall  # noqa: E402

# 合并路由（子路由器无 prefix，由顶层 /api 统一提供）
router.include_router(_customers)
router.include_router(_discovery)
router.include_router(_sync)
router.include_router(_config)
router.include_router(_hunter)
router.include_router(_tomba)
router.include_router(_waterfall)

