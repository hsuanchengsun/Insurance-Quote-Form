from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_user
from app.models import User
from app.web import templates


router = APIRouter()


@router.get("/profile")
def profile_page(request: Request, user: User = Depends(require_user)):
    return templates.TemplateResponse(request, "app/profile.html", {"user": user})


@router.post("/profile")
def update_profile(
    display_name: str = Form(...),
    chinese_name: str = Form(""),
    email: str = Form(...),
    phone: str = Form(...),
    license_number: str = Form(""),
    office_address: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    user.display_name = display_name.strip()
    user.chinese_name = chinese_name.strip() or None
    user.email = email.strip()
    user.phone = phone.strip()
    user.license_number = license_number.strip() or None
    user.office_address = office_address.strip() or None
    db.commit()
    return RedirectResponse("/profile?saved=1", status_code=303)

