import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

COOKIE_NAME = "squad_token"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def _decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def get_current_user(
    authorization: str | None = Header(default=None),
    squad_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    raw_token: str | None = None
    if squad_token:
        raw_token = squad_token
    elif authorization and authorization.startswith("Bearer "):
        raw_token = authorization[7:]

    if not raw_token:
        raise credentials_exc

    user_id = _decode_token(raw_token)
    if not user_id:
        raise credentials_exc

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        logger.warning("Auth attempt with valid token but missing/inactive user: %s", user_id)
        raise credentials_exc

    return user
