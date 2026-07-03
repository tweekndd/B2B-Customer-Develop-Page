"""
用户管理 API（V4.0 新增 / V4.1 新增权限管理）
仅管理员可操作：查看用户列表、新增用户、删除用户、修改密码、管理权限
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session as DBSession
from app.database import get_db, User
from app.auth import hash_password, require_admin

router = APIRouter(prefix="/users", tags=["用户管理"])


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class UpdatePasswordRequest(BaseModel):
    password: str


class UpdatePermissionsRequest(BaseModel):
    search_depth_limit: Optional[int] = None
    search_quota: Optional[int] = None
    ai_analysis_enabled: Optional[bool] = None
    email_finding_enabled: Optional[bool] = None


@router.get("/")
def list_users(admin=Depends(require_admin), db: DBSession = Depends(get_db)):
    """获取所有用户列表（V4.1 新增权限字段）"""
    users = db.query(User).order_by(User.id).all()
    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "is_active": bool(u.is_active),
                "created_at": u.created_at.isoformat() if u.created_at else None,
                # V4.1 权限字段
                "search_depth_limit": u.search_depth_limit or 50,
                "search_quota": u.search_quota or 100,
                "searches_used": u.searches_used or 0,
                "ai_analysis_enabled": bool(u.ai_analysis_enabled),
                "email_finding_enabled": bool(u.email_finding_enabled),
            }
            for u in users
        ]
    }


@router.post("/")
def create_user(
    req: CreateUserRequest,
    admin=Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """新增用户"""
    username = req.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")

    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="密码长度至少 4 位")

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"用户名 '{username}' 已存在")

    role = req.role if req.role in ("admin", "user") else "user"

    user = User(
        username=username,
        password_hash=hash_password(req.password),
        role=role,
        is_active=1,
    )
    db.add(user)
    db.commit()

    return {
        "success": True,
        "message": f"用户 '{username}' 创建成功",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        },
    }


@router.put("/{user_id}/password")
def update_password(
    user_id: int,
    req: UpdatePasswordRequest,
    admin=Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """修改用户密码"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="密码长度至少 4 位")

    user.password_hash = hash_password(req.password)
    db.commit()

    return {"success": True, "message": f"用户 '{user.username}' 密码已更新"}


@router.put("/{user_id}/role")
def update_role(
    user_id: int,
    req: dict,
    admin=Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """修改用户角色"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    new_role = req.get("role")
    if new_role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="角色必须是 admin 或 user")

    # 防止最后一个管理员把自己降级
    if user.role == "admin" and new_role != "admin":
        admin_count = db.query(User).filter(User.role == "admin", User.is_active == 1).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="无法降级最后一个管理员")

    user.role = new_role
    db.commit()

    return {"success": True, "message": f"用户 '{user.username}' 角色已更新为 {new_role}"}


@router.put("/{user_id}/toggle-active")
def toggle_active(
    user_id: int,
    admin=Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """启用/禁用用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 防止禁用最后一个管理员
    if user.role == "admin":
        admin_count = db.query(User).filter(User.role == "admin", User.is_active == 1).count()
        if admin_count <= 1 and user.is_active:
            raise HTTPException(status_code=400, detail="无法禁用最后一个管理员")

    user.is_active = 0 if user.is_active else 1
    db.commit()

    status_text = "已启用" if user.is_active else "已禁用"
    return {"success": True, "message": f"用户 '{user.username}' {status_text}"}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    admin=Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """删除用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 防止删除最后一个管理员
    if user.role == "admin":
        admin_count = db.query(User).filter(User.role == "admin", User.is_active == 1).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="无法删除最后一个管理员")

    username = user.username
    db.delete(user)
    db.commit()

    return {"success": True, "message": f"用户 '{username}' 已删除"}


@router.put("/{user_id}/permissions")
def update_permissions(
    user_id: int,
    req: UpdatePermissionsRequest,
    admin=Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """修改用户功能权限（V4.1 新增：搜索深度/配额/AI/邮箱开关）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    updates = []
    if req.search_depth_limit is not None:
        if req.search_depth_limit < 1:
            raise HTTPException(status_code=400, detail="搜索深度至少为 1")
        user.search_depth_limit = req.search_depth_limit
        updates.append("搜索深度")

    if req.search_quota is not None:
        if req.search_quota < 0:
            raise HTTPException(status_code=400, detail="搜索配额不能为负数")
        user.search_quota = req.search_quota
        updates.append("搜索配额")

    if req.ai_analysis_enabled is not None:
        user.ai_analysis_enabled = 1 if req.ai_analysis_enabled else 0
        updates.append("AI 分析权限")

    if req.email_finding_enabled is not None:
        user.email_finding_enabled = 1 if req.email_finding_enabled else 0
        updates.append("邮箱查找权限")

    db.commit()

    return {
        "success": True,
        "message": f"用户 '{user.username}' 权限已更新: {', '.join(updates)}",
    }


@router.post("/{user_id}/reset-quota")
def reset_search_quota(
    user_id: int,
    admin=Depends(require_admin),
    db: DBSession = Depends(get_db),
):
    """重置用户已使用的搜索次数为 0"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.searches_used = 0
    db.commit()
    return {
        "success": True,
        "message": f"用户 '{user.username}' 已使用搜索次数已重置为 0",
    }
