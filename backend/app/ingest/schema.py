"""Canonical security event schema. Every upload format is normalized to this shape."""

import ipaddress
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Category = Literal["auth", "network"]
Outcome = Literal["success", "failure", "allowed", "denied"]

# Common alternative column names seen in real log exports -> canonical names.
FIELD_ALIASES: dict[str, str] = {
    "@timestamp": "timestamp",
    "time": "timestamp",
    "event_time": "timestamp",
    "ts": "timestamp",
    "user": "username",
    "user_name": "username",
    "account": "username",
    "source_ip": "src_ip",
    "src": "src_ip",
    "client_ip": "src_ip",
    "ip": "src_ip",
    "destination_ip": "dst_ip",
    "dst": "dst_ip",
    "destination_port": "dst_port",
    "port": "dst_port",
    "result": "outcome",
    "status": "outcome",
    "event_type": "category",
    "type": "category",
    "proto": "protocol",
    "ua": "user_agent",
    "geo": "country",
}

CANONICAL_FIELDS = {
    "timestamp",
    "category",
    "action",
    "outcome",
    "username",
    "src_ip",
    "dst_ip",
    "dst_port",
    "protocol",
    "user_agent",
    "country",
}


def _blank_to_none(v: object) -> object:
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


class EventIn(BaseModel):
    """One validated row. Raises ValidationError with a readable reason on bad input."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    timestamp: datetime
    category: Category
    action: str = Field(min_length=1, max_length=50)
    outcome: Outcome
    src_ip: str
    username: str | None = Field(None, max_length=128)
    dst_ip: str | None = None
    dst_port: int | None = Field(None, ge=0, le=65535)
    protocol: str | None = Field(None, max_length=16)
    user_agent: str | None = Field(None, max_length=500)
    country: str | None = Field(None, pattern=r"^[A-Za-z]{2}$")

    @field_validator(
        "username", "dst_ip", "dst_port", "protocol", "user_agent", "country", mode="before"
    )
    @classmethod
    def blanks(cls, v: object) -> object:
        return _blank_to_none(v)

    @field_validator("category", "outcome", "action", "protocol", mode="before")
    @classmethod
    def lower(cls, v: object) -> object:
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator("country")
    @classmethod
    def upper_country(cls, v: str | None) -> str | None:
        return v.upper() if v else v

    @field_validator("src_ip", "dst_ip")
    @classmethod
    def valid_ip(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            return str(ipaddress.ip_address(v))
        except ValueError as exc:
            raise ValueError(f"'{v}' is not a valid IP address") from exc

    @field_validator("timestamp")
    @classmethod
    def assume_utc(cls, v: datetime) -> datetime:
        # Naive timestamps are treated as UTC; aware ones are converted to UTC.
        return v.replace(tzinfo=UTC) if v.tzinfo is None else v.astimezone(UTC)

    @model_validator(mode="after")
    def category_rules(self) -> "EventIn":
        if self.category == "auth":
            if not self.username:
                raise ValueError("auth events require a username")
            if self.outcome not in ("success", "failure"):
                raise ValueError("auth events must have outcome success or failure")
        if self.category == "network" and self.outcome not in ("allowed", "denied"):
            raise ValueError("network events must have outcome allowed or denied")
        return self
