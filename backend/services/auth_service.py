"""PostgreSQL-backed dashboard identity, sessions and role checks."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import psycopg2
import psycopg2.extras
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from backend.config import Settings, get_settings
from backend.models.auth import ModInvitePublic, Role, UserPublic
from backend.services.database import pooled_connection

bearer_scheme = HTTPBearer(auto_error=False)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${_b64(salt)}${_b64(digest)}"


def _verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, rounds, salt, digest = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(rounds))
        return hmac.compare_digest(actual, _unb64(digest))
    except (TypeError, ValueError):
        return False


class AuthStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._create_tables()
        self.bootstrap_root_admin()

    def _connect(self, readonly: bool = False):
        if not self.settings.faq_pg_dsn:
            raise RuntimeError("FAQ_PG_DSN is required for dashboard authentication.")
        # Every authenticated request re-reads the user row, so this must come
        # from the shared pool. A fresh connection to a remote Supabase costs
        # ~500ms of TCP+TLS handshake versus ~70ms for a pooled one.
        return pooled_connection(
            self.settings.faq_pg_dsn,
            self.settings.postgres_pool_min_size,
            self.settings.postgres_pool_max_size,
            readonly=readonly,
        )

    def _create_tables(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.app_users (
                    user_id UUID PRIMARY KEY, email TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
                    password_hash TEXT, google_subject TEXT UNIQUE,
                    role TEXT NOT NULL CHECK (role IN ('admin','mod')),
                    is_root_admin BOOLEAN NOT NULL DEFAULT FALSE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_login_at TIMESTAMPTZ, created_by UUID REFERENCES public.app_users(user_id),
                    CONSTRAINT app_users_root_must_be_admin CHECK (NOT is_root_admin OR role = 'admin'),
                    CONSTRAINT app_users_auth_method_check CHECK (password_hash IS NOT NULL OR google_subject IS NOT NULL)
                )
            """)
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS app_users_one_root_admin ON public.app_users (is_root_admin) WHERE is_root_admin")
            cur.execute("CREATE TABLE IF NOT EXISTS public.app_auth_revocations (jti TEXT PRIMARY KEY, expires_at TIMESTAMPTZ NOT NULL)")
            cur.execute("""CREATE TABLE IF NOT EXISTS public.app_mod_invites (
                email TEXT PRIMARY KEY, role TEXT NOT NULL DEFAULT 'mod' CHECK (role = 'mod'),
                invited_by UUID NOT NULL REFERENCES public.app_users(user_id),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )""")

    @staticmethod
    def _public(row: dict[str, Any]) -> UserPublic:
        return UserPublic.model_validate(row)

    def bootstrap_root_admin(self) -> None:
        email, password = self.settings.auth_root_admin_email.strip().lower(), self.settings.auth_root_admin_password
        if not email or not password:
            return
        with self._connect() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT user_id FROM public.app_users WHERE is_root_admin = TRUE")
            if cur.fetchone():
                return
            cur.execute("""INSERT INTO public.app_users
                (user_id,email,display_name,password_hash,role,is_root_admin,is_active)
                VALUES (%s,%s,%s,%s,'admin',TRUE,TRUE)""",
                (str(uuid4()), email, email.split("@")[0], _hash_password(password)))

    def list_users(self) -> list[UserPublic]:
        with self._connect(readonly=True) as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT user_id,email,display_name,role,is_root_admin,is_active,created_at,last_login_at FROM public.app_users ORDER BY is_root_admin DESC, created_at")
            return [self._public(dict(row)) for row in cur.fetchall()]

    def get_user(self, user_id: UUID) -> UserPublic | None:
        # The hottest query in the app: one lookup per authenticated request.
        with self._connect(readonly=True) as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT user_id,email,display_name,role,is_root_admin,is_active,created_at,last_login_at FROM public.app_users WHERE user_id=%s", (str(user_id),))
            row = cur.fetchone()
            return self._public(dict(row)) if row else None

    def create_user(self, *, email: str, display_name: str, role: Role, password: str, created_by: UUID) -> UserPublic:
        with self._connect() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            try:
                cur.execute("""INSERT INTO public.app_users (user_id,email,display_name,password_hash,role,created_by)
                    VALUES (%s,%s,%s,%s,%s,%s) RETURNING user_id,email,display_name,role,is_root_admin,is_active,created_at,last_login_at""",
                    (str(uuid4()), email.lower(), display_name.strip(), _hash_password(password), role, str(created_by)))
            except psycopg2.IntegrityError as exc:
                raise ValueError("Email này đã có tài khoản.") from exc
            return self._public(dict(cur.fetchone()))

    def invite_mod(self, email: str, invited_by: UUID) -> ModInvitePublic:
        normalized = email.strip().lower()
        with self._connect() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT 1 FROM public.app_users WHERE lower(email)=lower(%s)", (normalized,))
            if cur.fetchone():
                raise ValueError("Email này đã có tài khoản.")
            cur.execute("""INSERT INTO public.app_mod_invites (email, invited_by) VALUES (%s, %s)
                ON CONFLICT (email) DO UPDATE SET invited_by=EXCLUDED.invited_by, created_at=NOW()
                RETURNING email, role, invited_by, created_at""", (normalized, str(invited_by)))
            return ModInvitePublic.model_validate(dict(cur.fetchone()))

    def list_mod_invites(self) -> list[ModInvitePublic]:
        with self._connect(readonly=True) as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT email, role, invited_by, created_at FROM public.app_mod_invites ORDER BY created_at DESC")
            return [ModInvitePublic.model_validate(dict(row)) for row in cur.fetchall()]

    def delete_mod_invite(self, email: str) -> bool:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM public.app_mod_invites WHERE lower(email)=lower(%s)", (email.strip(),))
            return cur.rowcount > 0

    def update_role(self, user_id: UUID, role: Role) -> UserPublic:
        with self._connect() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT is_root_admin FROM public.app_users WHERE user_id=%s", (str(user_id),))
            row = cur.fetchone()
            if not row:
                raise KeyError(user_id)
            if row["is_root_admin"] and role != "admin":
                raise ValueError("Không thể hạ quyền Admin gốc.")
            cur.execute("UPDATE public.app_users SET role=%s, updated_at=NOW() WHERE user_id=%s RETURNING user_id,email,display_name,role,is_root_admin,is_active,created_at,last_login_at", (role, str(user_id)))
            return self._public(dict(cur.fetchone()))

    def update_status(self, user_id: UUID, is_active: bool) -> UserPublic:
        with self._connect() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT is_root_admin FROM public.app_users WHERE user_id=%s", (str(user_id),))
            row = cur.fetchone()
            if not row:
                raise KeyError(user_id)
            if row["is_root_admin"] and not is_active:
                raise ValueError("Không thể vô hiệu hoá Admin gốc.")
            cur.execute("UPDATE public.app_users SET is_active=%s, updated_at=NOW() WHERE user_id=%s RETURNING user_id,email,display_name,role,is_root_admin,is_active,created_at,last_login_at", (is_active, str(user_id)))
            return self._public(dict(cur.fetchone()))

    def delete_user(self, user_id: UUID) -> None:
        with self._connect() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT is_root_admin FROM public.app_users WHERE user_id=%s", (str(user_id),))
            row = cur.fetchone()
            if not row:
                raise KeyError(user_id)
            if row["is_root_admin"]:
                raise ValueError("Không thể xóa Admin gốc.")
            cur.execute("DELETE FROM public.app_users WHERE user_id=%s", (str(user_id),))

    def login_password(self, email: str, password: str) -> UserPublic | None:
        with self._connect() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT user_id,email,display_name,password_hash,role,is_root_admin,is_active,created_at,last_login_at FROM public.app_users WHERE lower(email)=lower(%s)", (email,))
            row = cur.fetchone()
            if not row or not row["is_active"] or not _verify_password(password, row["password_hash"]):
                return None
            cur.execute("UPDATE public.app_users SET last_login_at=NOW(), updated_at=NOW() WHERE user_id=%s", (str(row["user_id"]),))
            row["last_login_at"] = datetime.now(UTC)
            return self._public(dict(row))

    def login_google(self, subject: str, email: str, display_name: str, password: str | None = None) -> UserPublic | None:
        with self._connect() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT user_id,email,display_name,role,is_root_admin,is_active,created_at,last_login_at FROM public.app_users WHERE google_subject=%s OR lower(email)=lower(%s) FOR UPDATE", (subject, email))
            row = cur.fetchone()
            if not row:
                is_root = self.settings.auth_root_admin_email.strip().lower() == email.lower()
                if not is_root:
                    cur.execute("SELECT role FROM public.app_mod_invites WHERE lower(email)=lower(%s) FOR UPDATE", (email,))
                    invite = cur.fetchone()
                    if not invite:
                        raise PermissionError("EMAIL_NOT_INVITED")
                if not password or len(password) < 8:
                    raise ValueError("CREATE_PASSWORD_REQUIRED")
                cur.execute("""INSERT INTO public.app_users (user_id,email,display_name,google_subject,password_hash,role,is_root_admin)
                    VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING user_id,email,display_name,role,is_root_admin,is_active,created_at,last_login_at""",
                    (str(uuid4()), email, display_name, subject, _hash_password(password), "admin" if is_root else "mod", is_root))
                row = cur.fetchone()
                if not is_root:
                    cur.execute("DELETE FROM public.app_mod_invites WHERE lower(email)=lower(%s)", (email,))
            elif row:
                cur.execute("UPDATE public.app_users SET google_subject=COALESCE(google_subject,%s), last_login_at=NOW(), updated_at=NOW() WHERE user_id=%s", (subject, str(row["user_id"])))
            if not row or not row["is_active"]:
                return None
            row["last_login_at"] = datetime.now(UTC)
            return self._public(dict(row))


_store: AuthStore | None = None
def get_auth_store() -> AuthStore:
    global _store
    if _store is None: _store = AuthStore()
    return _store


def _secret(settings: Settings) -> bytes:
    if settings.auth_jwt_secret: return settings.auth_jwt_secret.encode()
    if settings.app_env == "production": raise RuntimeError("AUTH_JWT_SECRET is required in production.")
    return b"development-only-change-auth-jwt-secret"


def issue_token(user: UserPublic, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    now = datetime.now(UTC)
    payload = {"sub": str(user.user_id), "role": user.role, "jti": secrets.token_urlsafe(16), "iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=settings.auth_access_token_minutes)).timestamp())}
    head = _b64(json.dumps({"alg":"HS256","typ":"JWT"}, separators=(",", ":")).encode())
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64(hmac.new(_secret(settings), f"{head}.{body}".encode(), hashlib.sha256).digest())
    return f"{head}.{body}.{signature}"


# Sync on purpose: the body makes a blocking PostgreSQL call, so FastAPI must be
# free to run it on the threadpool. As `async def` it would block the event loop
# and serialize every request in flight.
def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> UserPublic:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cần đăng nhập.", headers={"WWW-Authenticate": "Bearer"})
    try:
        head, body, signature = credentials.credentials.split(".")
        expected = _b64(hmac.new(_secret(get_settings()), f"{head}.{body}".encode(), hashlib.sha256).digest())
        payload = json.loads(_unb64(body))
        if not hmac.compare_digest(expected, signature) or payload["exp"] < datetime.now(UTC).timestamp(): raise ValueError
        user = get_auth_store().get_user(UUID(payload["sub"]))
        if not user or not user.is_active: raise ValueError
        return user
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn.", headers={"WWW-Authenticate": "Bearer"}) from exc


def require_roles(*roles: Role):
    def dependency(user: UserPublic = Depends(current_user)) -> UserPublic:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền truy cập chức năng này.")
        return user
    return dependency


def verify_google(credential: str) -> tuple[str, str, str]:
    settings = get_settings()
    if not settings.google_oauth_client_id:
        raise HTTPException(status_code=503, detail="Google đăng nhập chưa được cấu hình.")
    try:
        claims = id_token.verify_oauth2_token(credential, google_requests.Request(), settings.google_oauth_client_id)
        return str(claims["sub"]), str(claims["email"]).lower(), str(claims.get("name") or claims["email"])
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Google credential không hợp lệ.") from exc
