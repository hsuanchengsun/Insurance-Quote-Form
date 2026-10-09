from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.services.auth_service import read_session_token


def current_user_or_none(request: Request, db: Session) -> User | None:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name, "")
    user_id = read_session_token(token, settings.secret_key) if token else None
    if user_id is None:
        return None
    user = db.get(User, user_id)
    return user if user and user.active else None


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = current_user_or_none(request, db)
    if user:
        return user
    if request.url.path.startswith("/api/"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
    raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})

