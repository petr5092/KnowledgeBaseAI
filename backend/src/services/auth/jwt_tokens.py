from datetime import datetime, timedelta, timezone

import jwt

from src.config.settings import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int, role: str) -> str:
    secret = settings.jwt_secret_key.get_secret_value()
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY is not configured")
    exp = _now() + timedelta(seconds=settings.jwt_access_ttl_seconds)
    payload = {"sub": str(user_id), "role": role, "type": "access", "exp": exp}
    return jwt.encode(payload, secret, algorithm="HS256")


def create_refresh_token(user_id: int) -> str:
    secret = settings.jwt_secret_key.get_secret_value()
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY is not configured")
    exp = _now() + timedelta(seconds=settings.jwt_refresh_ttl_seconds)
    payload = {"sub": str(user_id), "type": "refresh", "exp": exp}
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    secret = settings.jwt_secret_key.get_secret_value()
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY is not configured")
    return jwt.decode(token, secret, algorithms=["HS256"])
