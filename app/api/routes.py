"""
兼容性重导出模块（V2.8 重构）
原有单体路由已拆分为 customers.py / discovery.py / sync.py，
此文件保留以兼容 main.py 中 `from app.api.routes import router` 的导入路径。
新代码建议直接从 `app.api` 导入。
"""
from app.api import router  # noqa: F401
