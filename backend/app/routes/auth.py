import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.auth.jwt import (
    COOKIE_NAME,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

_COOKIE_OPTS = dict(
    key=COOKIE_NAME,
    httponly=True,
    samesite="strict",
    secure=settings.is_production,  # HTTPS only in prod
    max_age=settings.access_token_expire_minutes * 60,
    path="/",
)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        # Constant-time response — don't reveal whether email exists
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
    # Always run verify_password to prevent timing attacks
    password_ok = verify_password(payload.password, user.password_hash) if user else False
    if not user or not password_ok:
        logger.warning(
            "Failed login attempt for email=%s from ip=%s",
            payload.email,
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(str(user.id))
    response.set_cookie(value=token, **_COOKIE_OPTS)
    logger.info("User logged in: %s", user.id)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
