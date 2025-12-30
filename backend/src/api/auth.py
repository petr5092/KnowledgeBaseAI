from fastapi import APIRouter, HTTPException, Header
import psycopg2
from pydantic import BaseModel

from src.services.auth.jwt_tokens import create_access_token, create_refresh_token, decode_token
from src.services.auth.passwords import hash_password, verify_password
from src.services.auth.users_repo import create_user, get_user_by_email, get_user_by_id
from pydantic import BaseModel
import os

router = APIRouter(prefix="/v1/auth", tags=["Аутентификация"])


class RegisterPayload(BaseModel):
    email: str
    password: str


class LoginPayload(BaseModel):
    email: str
    password: str


class RefreshPayload(BaseModel):
    refresh_token: str

class RegisterResponse(BaseModel):
    ok: bool
    id: int
    email: str
    model_config = {
        "json_schema_extra": {
            "examples": [{"ok": True, "id": 42, "email": "user@example.com"}]
        }
    }

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    model_config = {
        "json_schema_extra": {
            "examples": [{"access_token": "eyJ...","refresh_token":"eyJ...","token_type":"bearer"}]
        }
    }

class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    model_config = {
        "json_schema_extra": {
            "examples": [{"access_token": "eyJ...","refresh_token":"eyJ...","token_type":"bearer"}]
        }
    }

class MeResponse(BaseModel):
    id: int
    email: str
    role: str
    model_config = {
        "json_schema_extra": {
            "examples": [{"id": 42, "email": "user@example.com", "role": "admin"}]
        }
    }

def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        return None
    if parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


@router.post("/register", summary="Регистрация", description="Создает пользователя и возвращает его идентификатор и email.", response_model=RegisterResponse)
def register(payload: RegisterPayload):
    """
    Принимает:
      - email: почта пользователя
      - password: пароль в открытом виде

    Возвращает:
      - ok: True
      - id: идентификатор пользователя
      - email: почта пользователя
    """
    if not (os.environ.get("PG_DSN") or "").strip():
        raise HTTPException(status_code=503, detail="postgres not configured")
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


@router.post("/login", summary="Вход", description="Проверяет учетные данные и возвращает пару токенов (access/refresh).", response_model=LoginResponse)
def login(payload: LoginPayload):
    """
    Принимает:
      - email: почта пользователя
      - password: пароль

    Возвращает:
      - access_token: JWT-токен доступа
      - refresh_token: JWT-токен обновления
      - token_type: 'bearer'
    """
    if not (os.environ.get("PG_DSN") or "").strip():
        raise HTTPException(status_code=503, detail="postgres not configured")
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


@router.post("/refresh", summary="Обновление токена", description="Обновляет пару токенов по действительному refresh токену.", response_model=RefreshResponse)
def refresh(payload: RefreshPayload):
    """
    Принимает:
      - refresh_token: валидный токен обновления

    Возвращает:
      - access_token: новый токен доступа
      - refresh_token: новый токен обновления
      - token_type: 'bearer'
    """
    if not (os.environ.get("PG_DSN") or "").strip():
        raise HTTPException(status_code=503, detail="postgres not configured")
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


@router.get("/me", summary="Текущий пользователь", description="Возвращает информацию о пользователе по access-токену.", response_model=MeResponse)
def me(authorization: str | None = Header(default=None)):
    """
    Принимает:
      - Authorization: заголовок формата 'Bearer <access_token>'

    Возвращает:
      - id: идентификатор пользователя
      - email: почта
      - role: роль пользователя
    """
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
