"""
AI Trade Customer Analyzer V3.2.6 - 主程序入口
客户发现 + 客户分析 + 客户数据库平台
V3.2.6: Firecrawl 智能降级 — 三层兜底 + 性价比最优
"""
import os
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import init_db, get_db
from app.services.cache_manager import clean_expired_cache
from app.api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：替代已弃用的 @app.on_event"""
    init_db()

    # 启动时清理过期缓存
    try:
        db_session = next(get_db())
        cleaned = clean_expired_cache(db_session)
        total = sum(cleaned.values())
        if total > 0:
            print(f"  缓存清理: 已删除 {total} 条过期记录 ({cleaned})")
        db_session.close()
    except Exception as e:
        print(f"  缓存清理跳过: {e}")

    print("=" * 50)
    print("  AI Trade Customer Analyzer V3.2.6")
    print(" 客户发现 + AI分析 + 客户数据库 + Hunter + Prospeo 邮箱 + 地图 + Firecrawl 降级")
    print("=" * 50)
    print(" 访问地址: http://localhost:8000")
    print(" 客户列表: http://localhost:8000")
    print(" 客户发现: http://localhost:8000/discovery")
    print(" 评分配置: http://localhost:8000/config")
    print(" Hunter邮箱: http://localhost:8000/hunter")
    print(" 地图页面:  http://localhost:8000/map")
    print("=" * 50)
    yield


templates = Jinja2Templates(directory="app/templates")

app = FastAPI(
    title="AI Trade Customer Analyzer V3.2.6",
    description="客户发现 + AI分析 + 客户数据库 + Hunter 邮箱查找 + Prospeo 邮箱发现 + 城市级地图 + Firecrawl 降级",
    version="3.2.6",
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


@app.get("/map")
async def map_page(request: Request):
    return templates.TemplateResponse("map.html", {"request": request, "active_nav": "map"})


@app.post("/admin/cleanup-cache")
def cleanup_cache(db: Session = Depends(get_db)):
    """手动触发所有过期缓存清理"""
    cleaned = clean_expired_cache(db)
    total = sum(cleaned.values())
    return {"message": f"已清理 {total} 条过期记录", "details": cleaned}


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
