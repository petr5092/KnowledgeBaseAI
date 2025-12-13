from fastapi import APIRouter, HTTPException, Header
import psycopg2
from pydantic import BaseModel

from src.services.auth.jwt_tokens import create_access_token, create_refresh_token, decode_token
from src.services.auth.passwords import hash_password, verify_password
from src.services.auth.users_repo import create_user, get_user_by_email, get_user_by_id

router = APIRouter(prefix="/v1/auth")


class RegisterPayload(BaseModel):
    email: str
    password: str


class LoginPayload(BaseModel):
    email: str
    password: str


class RefreshPayload(BaseModel):
    refresh_token: str


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        return None
    if parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


@router.post("/register")
def register(payload: RegisterPayload):
    try:
        existing = get_user_by_email(payload.email)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="postgres not configured")
    if existing is not None:
        raise HTTPException(status_code=409, detail="user already exists")
    try:
        user = create_user(email=payload.email, password_hash=hash_password(payload.password), role="user")
    except psycopg2.Error:
        raise HTTPException(status_code=500, detail="db error")
    return {"ok": True, "id": user.id, "email": user.email}


@router.post("/login")
def login(payload: LoginPayload):
    try:
        user = get_user_by_email(payload.email)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="postgres not configured")
    if user is None:
        raise HTTPException(status_code=401, detail="invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="user disabled")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    return {
        "access_token": create_access_token(user_id=user.id, role=user.role),
        "refresh_token": create_refresh_token(user_id=user.id),
        "token_type": "bearer",
    }


@router.post("/refresh")
def refresh(payload: RefreshPayload):
    try:
        data = decode_token(payload.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")
    if data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="invalid token")
    try:
        user_id = int(data.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")
    try:
        user = get_user_by_id(user_id)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="postgres not configured")
    if user is None:
        raise HTTPException(status_code=401, detail="invalid token")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="user disabled")
    return {
        "access_token": create_access_token(user_id=user.id, role=user.role),
        "refresh_token": create_refresh_token(user_id=user.id),
        "token_type": "bearer",
    }


@router.get("/me")
def me(authorization: str | None = Header(default=None)):
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
    try:
        user = get_user_by_id(user_id)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="postgres not configured")
    if user is None:
        raise HTTPException(status_code=401, detail="invalid token")
    return {"id": user.id, "email": user.email, "role": user.role}
