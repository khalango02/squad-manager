import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import RefreshToken, User

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_COOKIE = "squad_token"
REFRESH_COOKIE = "squad_refresh"
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ── Access token ─────────────────────────────────────────────────────────────

def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "access"},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def _decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


# ── Refresh token ─────────────────────────────────────────────────────────────

def create_refresh_token(user_id: str, db: Session) -> str:
    raw = secrets.token_urlsafe(48)
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    db.add(RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=expires,
    ))
    db.commit()
    return raw


def rotate_refresh_token(raw_token: str, db: Session) -> tuple[str, str] | None:
    """
    Validates the refresh token and returns (new_access, new_refresh).
    If the token was already revoked, ALL user tokens are revoked (theft detection).
    Returns None if invalid.
    """
    token_hash = _hash_token(raw_token)
    record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if not record:
        return None

    if record.revoked:
        # Token reuse detected — revoke entire family to limit blast radius
        logger.warning("Refresh token reuse detected for user %s — revoking all tokens", record.user_id)
        db.query(RefreshToken).filter(RefreshToken.user_id == record.user_id).update({"revoked": True})
        db.commit()
        return None

    if record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return None

    # Rotate: revoke old, issue new pair
    record.revoked = True
    db.commit()

    new_access = create_access_token(str(record.user_id))
    new_refresh = create_refresh_token(str(record.user_id), db)
    return new_access, new_refresh


def revoke_all_refresh_tokens(user_id: str, db: Session) -> None:
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False,  # noqa: E712
    ).update({"revoked": True})
    db.commit()


# ── Account lockout ───────────────────────────────────────────────────────────

def check_lockout(user: User) -> None:
    if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account locked. Try again after {user.locked_until.strftime('%H:%M UTC')}",
        )


def record_failed_login(user: User, db: Session) -> None:
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
        logger.warning("Account locked due to too many failures: %s", user.id)
    db.commit()


def reset_failed_login(user: User, db: Session) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()


# ── Dependency ────────────────────────────────────────────────────────────────

def get_current_user(
    authorization: str | None = Header(default=None),
    squad_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    raw_token: str | None = squad_token
    if not raw_token and authorization and authorization.startswith("Bearer "):
        raw_token = authorization[7:]

    if not raw_token:
        raise credentials_exc

    user_id = _decode_access_token(raw_token)
    if not user_id:
        raise credentials_exc

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exc

    return user
