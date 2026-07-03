"""
用户管理 API（V4.0 新增）
仅管理员可操作：查看用户列表、新增用户、删除用户、修改密码
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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


@router.get("/")
def list_users(admin=Depends(require_admin), db: DBSession = Depends(get_db)):
    """获取所有用户列表"""
    users = db.query(User).order_by(User.id).all()
    return {
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "is_active": bool(u.is_active),
                "created_at": u.created_at.isoformat() if u.created_at else None,
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
