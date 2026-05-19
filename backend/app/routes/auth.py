import logging

import jwt as pyjwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.auth.jwt import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    check_lockout,
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    record_failed_login,
    reset_failed_login,
    revoke_all_refresh_tokens,
    rotate_refresh_token,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

_COOKIE_BASE = dict(httponly=True, samesite="strict", path="/")


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    opts = {**_COOKIE_BASE, "secure": settings.is_production}
    response.set_cookie(ACCESS_COOKIE, access_token, max_age=settings.access_token_expire_minutes * 60, **opts)
    response.set_cookie(REFRESH_COOKIE, refresh_token, max_age=settings.refresh_token_expire_days * 86400, **opts)


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Registration failed")
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("New user registered: %s", user.id)
    return user


@router.post("/login", response_model=UserOut)
@limiter.limit("5/minute")
def login(
    request: Request,
    response: Response,
    payload: UserCreate,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email).first()

    # Always run argon2 to prevent user-enumeration via timing
    _DUMMY_HASH = "$argon2id$v=19$m=65536,t=2,p=2$dummysaltdummysaltdummy$dummyhashvaluedummyhashvaluedummy"
    password_ok = verify_password(payload.password, user.password_hash if user else _DUMMY_HASH)

    if not user or not password_ok:
        if user:
            record_failed_login(user, db)
        logger.warning(
            "Failed login for email=%s ip=%s",
            payload.email,
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    check_lockout(user)
    reset_failed_login(user, db)

    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id), db)
    _set_auth_cookies(response, access, refresh)
    logger.info("User logged in: %s", user.id)
    return user


@router.post("/refresh", response_model=UserOut)
def refresh(
    response: Response,
    squad_refresh: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if not squad_refresh:
        raise HTTPException(status_code=401, detail="No refresh token")

    result = rotate_refresh_token(squad_refresh, db)
    if not result:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    new_access, new_refresh = result
    _set_auth_cookies(response, new_access, new_refresh)

    payload = pyjwt.decode(new_access, settings.secret_key, algorithms=[settings.algorithm])
    user = db.query(User).filter(User.id == payload["sub"]).first()
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    revoke_all_refresh_tokens(str(current_user.id), db)
    _clear_auth_cookies(response)
    logger.info("User logged out: %s", current_user.id)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
