"""
AI Trade Customer Analyzer V3.5.0 - 主程序入口
V3.5.0: 更换AI引擎为智谱GLM-4.7-Flash（免费）
客户发现 + 客户分析 + 客户数据库平台
"""
import os
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session
from app.database import init_db, get_db
from app.services.cache_manager import clean_expired_cache
from app.auth import get_user_from_session, get_current_user, require_admin, ensure_admin_exists
from app.api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    init_db()

    try:
        db_session = next(get_db())
        cleaned = clean_expired_cache(db_session)
        total = sum(cleaned.values())
        if total > 0:
            print(f"  缓存清理: 已删除 {total} 条过期记录 ({cleaned})")

        # 启动时检查管理员账号
        ensure_admin_exists(db_session)
        db_session.close()
    except Exception as e:
        print(f"  初始化跳过: {e}")

    print("=" * 50)
    print("  AI Trade Customer Analyzer V3.5.0")
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


# Python 3.14 兼容：关闭 Jinja2 模板缓存（Python 3.14 的 weakref 变更影响缓存键）
_jinja_env = Environment(
    loader=FileSystemLoader("app/templates"),
    cache_size=0,  # 禁用缓存以兼容 Python 3.14（0=None 无缓存）
)
templates = Jinja2Templates(env=_jinja_env)

app = FastAPI(
    title="AI Trade Customer Analyzer V3.5.0",
    description="客户发现 + AI分析 + 客户数据库 + Hunter 邮箱查找 + Prospeo 邮箱发现 + 城市级地图 + Firecrawl 降级 — V3.5.0 GLM免费AI引擎",
    version="3.5.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(router)


# ── API 认证中间件 ──
# 注意：必须定义在 add_middleware(SessionMiddleware) 之前，
# 这样 SessionMiddleware 会成为外层，先处理 session 再进入此中间件
@app.middleware("http")
async def api_auth_middleware(request: Request, call_next):
    """API 请求必须登录（/api/auth/* 除外），未登录返回 401"""
    path = request.url.path
    if path.startswith("/api/") and not path.startswith("/api/auth/"):
        user_id = request.session.get("user_id")
        if user_id is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "请先登录"},
            )
    return await call_next(request)


# ── Session 会话中间件（最后添加，成为最外层，优先处理 session）──
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "customer-analyzer-session-secret-change-me"),
    max_age=86400 * 7,  # 7 天过期
)


# ── 辅助函数 ──

def _render(request: Request, template: str, **kwargs):
    """渲染模板，自动注入 current_user"""
    db_session = next(get_db())
    try:
        current_user = get_user_from_session(request, db_session)
        return templates.TemplateResponse(
            template,
            {"request": request, "current_user": current_user, **kwargs},
        )
    finally:
        db_session.close()


def _login_required_page(request: Request, template: str, **kwargs):
    """需登录的页面，未登录跳转到登录页"""
    db_session = next(get_db())
    try:
        user = get_user_from_session(request, db_session)
        if user is None:
            return RedirectResponse(url="/login?next=" + request.url.path, status_code=302)
        return templates.TemplateResponse(
            template,
            {"request": request, "current_user": user, **kwargs},
        )
    finally:
        db_session.close()


# ── 公开页面（无需登录）──

@app.get("/login")
async def login_page(request: Request):
    """登录页面（已登录则跳转首页）"""
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=302)
    return _render(request, "login.html")


@app.get("/")
async def index_page(request: Request):
    return _render(request, "index.html", active_nav="index")


@app.get("/customer/{customer_id}")
async def detail_page(request: Request, customer_id: int):
    return _render(request, "detail.html", active_nav="detail")


@app.get("/map")
async def map_page(request: Request):
    return _render(request, "map.html", active_nav="map")


# ── 需要登录的页面 ──

@app.get("/discovery")
async def discovery_page(request: Request):
    return _login_required_page(request, "discovery.html", active_nav="discovery")


@app.get("/config")
async def config_page(request: Request):
    return _login_required_page(request, "config.html", active_nav="config")


@app.get("/hunter")
async def hunter_page(request: Request):
    return _login_required_page(request, "hunter.html", active_nav="hunter")


@app.get("/sync")
async def sync_page(request: Request):
    return _login_required_page(request, "sync.html", active_nav="sync")


# ── 管理员页面 ──

@app.get("/users")
async def users_page(request: Request):
    """用户管理页面（仅管理员）"""
    db_session = next(get_db())
    try:
        user = get_user_from_session(request, db_session)
        if user is None:
            return RedirectResponse(url="/login?next=/users", status_code=302)
        if user.role != "admin":
            return RedirectResponse(url="/", status_code=302)
        return _render(request, "users.html", active_nav="users")
    finally:
        db_session.close()


# ── 管理接口 ──

@app.post("/admin/cleanup-cache")
def cleanup_cache(db: Session = Depends(get_db), admin=Depends(require_admin)):
    """手动触发所有过期缓存清理（仅管理员）"""
    cleaned = clean_expired_cache(db)
    total = sum(cleaned.values())
    return {"message": f"已清理 {total} 条过期记录", "details": cleaned}


if __name__ == "__main__":
    os.makedirs("app/uploads", exist_ok=True)
    os.makedirs("app/static/css", exist_ok=True)
    os.makedirs("app/templates", exist_ok=True)

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )
