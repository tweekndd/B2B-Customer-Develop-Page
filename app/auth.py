"""
认证与授权模块（V4.0 新增）
提供密码加密、Session 会话管理、角色权限检查
"""
import os
import bcrypt
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session as DBSession
from app.database import get_db, User


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码是否匹配"""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def get_user_from_session(request: Request, db: DBSession) -> User | None:
    """从 Session 获取已登录用户（非依赖注入版本，用于模板渲染）"""
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return db.query(User).filter(User.id == user_id, User.is_active == 1).first()


def get_current_user(request: Request, db: DBSession = Depends(get_db)):
    """FastAPI 依赖注入版本：从 Session 获取当前登录用户，未登录返回 None"""
    return get_user_from_session(request, db)


def require_user(current_user: User = Depends(get_current_user)):
    """要求用户必须登录（普通用户或管理员），未登录返回 401"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return current_user


def require_admin(current_user: User = Depends(get_current_user)):
    """要求用户必须是管理员，否则返回 403"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="权限不足，需要管理员账号")
    return current_user


def ensure_admin_exists(db: DBSession):
    """启动时检查是否存在管理员账号，没有则从环境变量创建"""
    admin = db.query(User).filter(User.role == "admin").first()
    if admin:
        return

    admin_username = os.environ.get("ADMIN_USERNAME", "").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "").strip()

    if not admin_username or not admin_password:
        print("  [用户系统] 未设置 ADMIN_USERNAME / ADMIN_PASSWORD 环境变量，跳过管理员创建")
        print("  [用户系统] 首次使用请设置环境变量，或在 VPS 上执行：")
        print("  [用户系统]   export ADMIN_USERNAME=admin")
        print("  [用户系统]   export ADMIN_PASSWORD=你的密码")
        print("  [用户系统] 然后重启服务即可自动创建管理员")
        return

    existing = db.query(User).filter(User.username == admin_username).first()
    if existing:
        if existing.role != "admin":
            existing.role = "admin"
            db.commit()
            print(f"  [用户系统] 用户 '{admin_username}' 已升级为管理员")
        return

    user = User(
        username=admin_username,
        password_hash=hash_password(admin_password),
        role="admin",
        is_active=1,
    )
    db.add(user)
    db.commit()
    print(f"  [用户系统] 管理员账号 '{admin_username}' 已创建")
