"""
用户认证 API（V4.0 新增）
登录 / 登出 / 获取当前用户信息
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from app.database import get_db, User
from app.auth import verify_password, get_current_user

router = APIRouter(prefix="/auth", tags=["认证"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(req: LoginRequest, request: Request, db: DBSession = Depends(get_db)):
    """用户登录"""
    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 写入 Session
    request.session["user_id"] = user.id

    return {
        "success": True,
        "message": "登录成功",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        },
    }


@router.post("/logout")
def logout(request: Request):
    """用户登出"""
    request.session.clear()
    return {"success": True, "message": "已退出登录"}


@router.get("/me")
def get_me(current_user=Depends(get_current_user)):
    """获取当前登录用户信息（未登录返回 null）"""
    if current_user is None:
        return {"user": None}
    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
        }
    }
