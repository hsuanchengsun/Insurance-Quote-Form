from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.services.audit_service import record_event
from app.services.auth_service import create_session_token, verify_password
from app.web import templates


router = APIRouter()


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "app/login.html", {"error": None})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == username, User.active.is_(True)))
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request, "app/login.html", {"error": "帳號或密碼不正確。"}, status_code=400
        )
    record_event(db, user.id, "login")
    db.commit()
    settings = get_settings()
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        settings.session_cookie_name,
        create_session_token(user.id, settings.secret_key),
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=28_800,
    )
    return response


@router.post("/logout")
def logout():
    settings = get_settings()
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response

