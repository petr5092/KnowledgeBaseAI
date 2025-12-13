from fastapi import Header, HTTPException

from src.services.auth.jwt_tokens import decode_token
from src.services.auth.users_repo import get_user_by_id


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        return None
    if parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def get_current_user(authorization: str | None = Header(default=None)):
    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="missing token")
    try:
        data = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")
    if data.get("type") != "access":
        raise HTTPException(status_code=401, detail="invalid token")
    try:
        user_id = int(data.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid token")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="user disabled")
    return user


def require_admin(authorization: str | None = Header(default=None)):
    user = get_current_user(authorization)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="forbidden")
    return user
