import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import Role
from app.schemas.common import ORMModel


def _check_password_strength(v: str) -> str:
    if len(v) < 10:
        raise ValueError("Password must be at least 10 characters")
    if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
        raise ValueError("Password must contain letters and numbers")
    return v


def _normalize_email(v: str) -> str:
    return v.strip().lower()


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(max_length=128)

    _strong = field_validator("password")(_check_password_strength)
    _email = field_validator("email", mode="after")(_normalize_email)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)

    _email = field_validator("email", mode="after")(_normalize_email)


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class UserBrief(ORMModel):
    id: uuid.UUID
    full_name: str
    email: EmailStr


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)

    _strong = field_validator("new_password")(_check_password_strength)


class AdminUserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None
