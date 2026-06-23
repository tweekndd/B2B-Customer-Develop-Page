"""
AI Trade Customer Analyzer V3.1.1 - 主程序入口
客户发现 + 客户分析 + 客户数据库平台
"""
import os
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from app.database import init_db
from app.api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：替代已弃用的 @app.on_event"""
    init_db()
    print("=" * 50)
    print("  AI Trade Customer Analyzer V3.1.1")
    print(" 客户发现 + AI分析 + 客户数据库 + Hunter 邮箱")
    print("=" * 50)
    print(" 访问地址: http://localhost:8000")
    print(" 客户列表: http://localhost:8000")
    print(" 客户发现: http://localhost:8000/discovery")
    print(" 评分配置: http://localhost:8000/config")
    print(" Hunter邮箱: http://localhost:8000/hunter")
    print("=" * 50)
    yield


templates = Jinja2Templates(directory="app/templates")

app = FastAPI(
    title="AI Trade Customer Analyzer V3.1.1",
    description="客户发现 + 客户分析 + 客户数据库平台 + Hunter 邮箱查找",
    version="3.1.1",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(router)


@app.get("/")
async def index_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "active_nav": "index"})


@app.get("/discovery")
async def discovery_page(request: Request):
    return templates.TemplateResponse("discovery.html", {"request": request, "active_nav": "discovery"})


@app.get("/customer/{customer_id}")
async def detail_page(request: Request, customer_id: int):
    return templates.TemplateResponse("detail.html", {"request": request, "active_nav": "detail"})


@app.get("/config")
async def config_page(request: Request):
    return templates.TemplateResponse("config.html", {"request": request, "active_nav": "config"})


@app.get("/hunter")
async def hunter_page(request: Request):
    return templates.TemplateResponse("hunter.html", {"request": request, "active_nav": "hunter"})


if __name__ == "__main__":
    os.makedirs("app/uploads", exist_ok=True)
    os.makedirs("app/static/css", exist_ok=True)
    os.makedirs("app/templates", exist_ok=True)

    # reload=False 避免 uvicorn 在 Windows 下 multiprocessing.spawn
    # 导致的部分路由未注册问题。如需热重载请使用：
    #   python -m uvicorn main:app --reload
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )
