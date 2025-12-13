from dataclasses import dataclass
from typing import Optional

import psycopg2

from src.config.settings import settings


@dataclass(frozen=True)
class User:
    id: int
    email: str
    password_hash: str
    role: str
    is_active: bool


def _get_conn():
    dsn = str(settings.pg_dsn) if settings.pg_dsn else ""
    if not dsn:
        return None
    return psycopg2.connect(dsn)


def ensure_users_table() -> None:
    conn = _get_conn()
    if conn is None:
        return
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
    conn.close()


def create_user(email: str, password_hash: str, role: str = "user") -> User:
    ensure_users_table()
    conn = _get_conn()
    if conn is None:
        raise RuntimeError("postgres not configured")
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users(email, password_hash, role) VALUES (%s,%s,%s) RETURNING id, email, password_hash, role, is_active",
                (email, password_hash, role),
            )
            row = cur.fetchone()
    conn.close()
    return User(id=row[0], email=row[1], password_hash=row[2], role=row[3], is_active=row[4])


def ensure_bootstrap_admin() -> None:
    email = (settings.bootstrap_admin_email or "").strip()
    password = settings.bootstrap_admin_password.get_secret_value()
    if not email or not password:
        return

    ensure_users_table()
    conn = _get_conn()
    if conn is None:
        return

    from src.services.auth.passwords import hash_password

    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email=%s", (email,))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE users SET role='admin', is_active=TRUE WHERE email=%s", (email,))
            else:
                cur.execute(
                    "INSERT INTO users(email, password_hash, role) VALUES (%s,%s,'admin')",
                    (email, hash_password(password)),
                )

    conn.close()


def get_user_by_email(email: str) -> Optional[User]:
    ensure_users_table()
    conn = _get_conn()
    if conn is None:
        raise RuntimeError("postgres not configured")
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, password_hash, role, is_active FROM users WHERE email=%s", (email,))
            row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return User(id=row[0], email=row[1], password_hash=row[2], role=row[3], is_active=row[4])


def get_user_by_id(user_id: int) -> Optional[User]:
    ensure_users_table()
    conn = _get_conn()
    if conn is None:
        raise RuntimeError("postgres not configured")
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, password_hash, role, is_active FROM users WHERE id=%s", (user_id,))
            row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return User(id=row[0], email=row[1], password_hash=row[2], role=row[3], is_active=row[4])
