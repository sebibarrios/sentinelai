import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Admin, Analyst, CurrentUser
from app.api.v1.auth import set_session_cookie
from app.core.errors import AppError, NotFound, Unauthorized
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models import User
from app.models.enums import Role
from app.schemas.common import Page, PageParams
from app.schemas.user import (
    AdminUserUpdate,
    PasswordChange,
    ProfileUpdate,
    UserBrief,
    UserOut,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserOut)
def update_profile(
    data: ProfileUpdate, user: User = CurrentUser, db: Session = Depends(get_db)
) -> User:
    user.full_name = data.full_name.strip()
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/password", status_code=204)
def change_password(
    data: PasswordChange,
    response: Response,
    user: User = CurrentUser,
    db: Session = Depends(get_db),
) -> None:
    if not verify_password(data.current_password, user.password_hash):
        raise Unauthorized("Current password is incorrect")
    user.password_hash = hash_password(data.new_password)
    # Sign out every other session (e.g. a stolen cookie), then keep this one signed in.
    user.session_version += 1
    db.commit()
    set_session_cookie(response, user)


@router.get("/assignable", response_model=list[UserBrief])
def assignable_users(_: User = Analyst, db: Session = Depends(get_db)) -> list[User]:
    """Analysts and admins who can own incidents (for the assignee picker)."""
    return list(
        db.scalars(
            select(User)
            .where(User.is_active.is_(True), User.role.in_([Role.analyst, Role.admin]))
            .order_by(User.full_name)
        ).all()
    )


@router.get("", response_model=Page[UserOut])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: User = Admin,
    db: Session = Depends(get_db),
) -> dict:
    params = PageParams(page=page, page_size=page_size)
    total = db.scalar(select(func.count()).select_from(User)) or 0
    items = db.scalars(
        select(User).order_by(User.created_at).offset(params.offset).limit(params.page_size)
    ).all()
    return {"items": items, "page": page, "page_size": page_size, "total": total}


@router.patch("/{user_id}", response_model=UserOut)
def admin_update_user(
    user_id: uuid.UUID,
    data: AdminUserUpdate,
    admin: User = Admin,
    db: Session = Depends(get_db),
) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise NotFound("User not found")
    if target.id == admin.id and (data.role not in (None, Role.admin) or data.is_active is False):
        # Prevents the last admin from locking everyone out by accident.
        raise AppError("You cannot demote or deactivate your own account")
    if data.role is not None:
        target.role = data.role
    if data.is_active is not None:
        if target.is_active and not data.is_active:
            target.session_version += 1  # end their sessions now, not at token expiry
        target.is_active = data.is_active
    db.commit()
    db.refresh(target)
    return target
