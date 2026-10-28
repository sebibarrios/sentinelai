import uuid
from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import Forbidden, Unauthorized
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.models.enums import Role

# Higher number = more privilege. require_role(Role.analyst) admits analysts and admins.
_ROLE_LEVEL = {Role.viewer: 1, Role.analyst: 2, Role.admin: 3}


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(get_settings().cookie_name)
    if not token:
        raise Unauthorized("Not authenticated")
    payload = decode_access_token(token)
    if payload is None:
        raise Unauthorized("Session expired or invalid")
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError as exc:
        raise Unauthorized("Session expired or invalid") from exc
    # Re-load from the DB on every request so role changes and deactivation apply immediately,
    # rather than trusting the role claim baked into the token.
    user = db.get(User, user_id)
    if user is None or not user.is_active or payload.get("sv") != user.session_version:
        # A session_version mismatch means the user signed out or changed password
        # since this token was issued.
        raise Unauthorized("Session expired or invalid")
    return user


def require_role(minimum: Role) -> Callable[..., User]:
    def checker(user: User = Depends(get_current_user)) -> User:
        if _ROLE_LEVEL[user.role] < _ROLE_LEVEL[minimum]:
            raise Forbidden(f"Requires {minimum.value} role or higher")
        return user

    return checker


CurrentUser = Depends(get_current_user)
Viewer = Depends(require_role(Role.viewer))
Analyst = Depends(require_role(Role.analyst))
Admin = Depends(require_role(Role.admin))
