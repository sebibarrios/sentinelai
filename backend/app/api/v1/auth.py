import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.core.errors import Conflict, Unauthorized
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.base import utcnow
from app.db.session import get_db
from app.models import User
from app.models.enums import Role
from app.schemas.user import UserLogin, UserOut, UserRegister
from app.services import rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


def set_session_cookie(response: Response, user: User) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.cookie_name,
        value=create_access_token(user.id, user.role.value, user.session_version),
        max_age=settings.access_token_minutes * 60,
        httponly=True,  # not readable by JavaScript -> XSS cannot steal it
        secure=settings.is_production,  # HTTPS-only in production
        samesite="lax",  # not sent on cross-site POSTs -> CSRF protection
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    data: UserRegister, request: Request, response: Response, db: Session = Depends(get_db)
) -> User:
    ip = rate_limit.client_ip(request)
    if ip is not None:
        # Count attempts, not just successes, so probing for taken emails is also limited.
        rate_limit.reserve(db, rate_limit.registrations_per_ip(), ip)
        db.commit()

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
    set_session_cookie(response, user)
    return user


@router.post("/login", response_model=UserOut)
def login(
    data: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)
) -> User:
    ip = rate_limit.client_ip(request)
    per_account = rate_limit.login_failures_per_account()
    per_ip = rate_limit.login_failures_per_ip()
    # Each attempt is counted *before* the password is checked, atomically with the
    # limit check, and committed straight away. So simultaneous guesses can't all slip
    # under the limit, and no lock is held during the slow password hash. During a
    # lockout even the right password is refused. Unknown emails are counted exactly
    # like real ones, so lockouts don't reveal which accounts exist.
    rate_limit.reserve(db, per_account, data.email)
    ip_hit = rate_limit.reserve(db, per_ip, ip) if ip is not None else None
    rate_limit.prune(db)
    db.commit()

    user = db.scalar(select(User).where(User.email == data.email))
    # verify_password runs even when the user is missing, so response time
    # doesn't reveal which emails are registered.
    valid = verify_password(data.password, user.password_hash if user else None)
    if not user or not valid or not user.is_active:
        raise Unauthorized("Invalid email or password")  # the reservations stay counted

    rate_limit.clear(db, per_account, data.email)
    rate_limit.release(db, ip_hit)
    user.last_login_at = utcnow()
    db.commit()
    set_session_cookie(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    """Ends every session for this user, not only this browser's.

    Clearing the cookie alone would leave a copied token usable until it expires;
    bumping session_version makes all previously issued tokens invalid immediately.
    """
    payload = decode_access_token(request.cookies.get(get_settings().cookie_name, ""))
    if payload:
        try:
            user = db.get(User, uuid.UUID(payload["sub"]))
        except ValueError:
            user = None
        if user and payload.get("sv") == user.session_version:
            user.session_version += 1
            db.commit()
    response.delete_cookie(get_settings().cookie_name, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = CurrentUser) -> User:
    return user
