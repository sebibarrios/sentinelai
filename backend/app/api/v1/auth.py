from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.core.errors import Conflict, Unauthorized
from app.core.security import create_access_token, hash_password, verify_password
from app.db.base import utcnow
from app.db.session import get_db
from app.models import User
from app.models.enums import Role
from app.schemas.user import UserLogin, UserOut, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.cookie_name,
        value=create_access_token(user.id, user.role.value),
        max_age=settings.access_token_minutes * 60,
        httponly=True,  # not readable by JavaScript -> XSS cannot steal it
        secure=settings.is_production,  # HTTPS-only in production
        samesite="lax",  # not sent on cross-site POSTs -> CSRF protection
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, response: Response, db: Session = Depends(get_db)) -> User:
    if db.scalar(select(User).where(User.email == data.email)):
        raise Conflict("An account with this email already exists")
    user = User(
        email=data.email,
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password),
        role=Role.viewer,  # least privilege; admins promote
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _set_session_cookie(response, user)
    return user


@router.post("/login", response_model=UserOut)
def login(data: UserLogin, response: Response, db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).where(User.email == data.email))
    # verify_password runs even when the user is missing, so response time
    # doesn't reveal which emails are registered.
    valid = verify_password(data.password, user.password_hash if user else None)
    if not user or not valid or not user.is_active:
        raise Unauthorized("Invalid email or password")
    user.last_login_at = utcnow()
    db.commit()
    _set_session_cookie(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(get_settings().cookie_name, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = CurrentUser) -> User:
    return user
