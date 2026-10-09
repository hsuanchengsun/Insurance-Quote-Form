from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import get_db
from app.dependencies import require_user
from app.models import GeneratedFile, Quote, QuoteVersion, User
from app.schemas.quote import GenerationRequest, QuoteDraft, QuoteLocale
from app.services.audit_service import record_event
from app.services.file_service import FileIntegrityError, resolve_verified_file
from app.services.gemini_service import GeminiExtractionError, extract_quote_from_pdf
from app.services.preset_service import get_coverage_presets
from app.services.quote_number_service import next_quote_number
from app.services.quote_service import copy_quote, create_quote, save_draft
from app.services.render_payload_service import build_render_payload
from app.services.rendering_service import RenderingUnavailable, render_html
from app.services.validation_service import validate_quote
from app.services.version_service import create_version
from app.web import templates



router = APIRouter()


def _get_quote_or_404(db: Session, quote_id: int) -> Quote:
    quote = db.get(Quote, quote_id)
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote


@router.get("/")
def quote_list(
    request: Request,
    q: str = Query(""),
    status_filter: str = Query(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    statement = select(Quote).order_by(Quote.updated_at.desc())
    if q.strip():
        value = f"%{q.strip()}%"
        statement = statement.where(or_(Quote.customer_name.ilike(value), Quote.quote_number.ilike(value)))
    if status_filter:
        statement = statement.where(Quote.status == status_filter)
    quotes = list(db.scalars(statement).all())
    today = date.today()
    for quote in quotes:
        if quote.status == "Generated" and quote.expiration_date < today:
            quote.display_status = "Expired"  # type: ignore[attr-defined]
        else:
            quote.display_status = quote.status  # type: ignore[attr-defined]
    return templates.TemplateResponse(
        request,
        "app/quote_list.html",
        {"user": user, "quotes": quotes, "q": q, "status_filter": status_filter},
    )


@router.post("/quotes")
def new_quote(user: User = Depends(require_user), db: Session = Depends(get_db)):
    quote = create_quote(db, user)
    return RedirectResponse(f"/quotes/{quote.id}/edit", status_code=303)


@router.post("/quotes/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    locale: str = Form("zh-TW"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if not file.filename:
        return JSONResponse({"ok": False, "message": "請選擇要上傳的 PDF 檔案。"}, status_code=400)
    
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith(".pdf") or file.content_type == "application/pdf"):
        return JSONResponse({"ok": False, "message": "僅支援上傳 PDF 格式文件。"}, status_code=400)

    # Read PDF content (limit 15MB)
    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        return JSONResponse({"ok": False, "message": "檔案大小超過 15MB 限制。"}, status_code=400)
    if len(content) == 0:
        return JSONResponse({"ok": False, "message": "上傳的 PDF 檔案為空。"}, status_code=400)

    # Validate locale
    selected_locale = QuoteLocale.ZH_TW
    try:
        selected_locale = QuoteLocale(locale)
    except ValueError:
        pass

    quote_number = next_quote_number(db)
    try:
        draft = extract_quote_from_pdf(
            pdf_bytes=content,
            user_id=user.id,
            quote_number=quote_number,
            locale=selected_locale,
        )
    except GeminiExtractionError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=422)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"處理 PDF 發生未預期的錯誤：{exc}"}, status_code=500)

    # Save uploaded file to uploads directory
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    safe_filename = f"{quote_number}_{Path(file.filename).name}"
    upload_path = uploads_dir / safe_filename
    try:
        upload_path.write_bytes(content)
    except Exception:
        pass

    # Create new Quote with extracted draft
    quote = Quote(
        quote_number=quote_number,
        customer_name=draft.customer.name.strip(),
        status="Draft",
        owner_user_id=user.id,
        current_draft_json=draft.model_dump(mode="json"),
        quote_date=draft.policy.quote_date,
        expiration_date=draft.policy.expiration_date,
    )
    db.add(quote)
    db.flush()
    record_event(db, user.id, "upload_pdf_extract", quote_id=quote.id, metadata={"filename": file.filename})
    db.commit()

    return {
        "ok": True,
        "quote_id": quote.id,
        "quote_number": quote.quote_number,
        "redirect_url": f"/quotes/{quote.id}/edit?from_pdf=1",
    }


@router.get("/quotes/{quote_id}/edit")
def edit_quote(
    quote_id: int,
    request: Request,
    from_pdf: int = Query(0),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    quote = _get_quote_or_404(db, quote_id)
    return templates.TemplateResponse(
        request,
        "app/quote_editor.html",
        {
            "user": user,
            "quote": quote,
            "draft": quote.current_draft_json,
            "presets": get_coverage_presets(),
            "from_pdf": bool(from_pdf),
        },
    )



@router.get("/quotes/{quote_id}")
def quote_detail(
    quote_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    quote = db.scalar(
        select(Quote)
        .where(Quote.id == quote_id)
        .options(selectinload(Quote.versions).selectinload(QuoteVersion.generated_files))
    )
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    return templates.TemplateResponse(request, "app/quote_detail.html", {"user": user, "quote": quote})


@router.put("/api/quotes/{quote_id}")
def update_quote(
    quote_id: int,
    draft: QuoteDraft,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    quote = _get_quote_or_404(db, quote_id)
    save_draft(db, quote, draft, user)
    return {"ok": True, "saved_at": datetime.utcnow().isoformat() + "Z"}


@router.post("/api/quotes/{quote_id}/validate")
def validate_quote_api(
    quote_id: int,
    draft: QuoteDraft,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    _get_quote_or_404(db, quote_id)
    agent = db.get(User, draft.agent_id)
    result = validate_quote(draft, agent)
    return {**result.model_dump(), "can_generate": result.can_generate}


@router.post("/api/quotes/{quote_id}/preview", response_class=HTMLResponse)
def preview_quote(
    quote_id: int,
    draft: QuoteDraft,
    output_type: str = Query("mobile_png", pattern="^(mobile_png|pdf)$"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    quote = _get_quote_or_404(db, quote_id)
    draft.quote_number = quote.quote_number
    agent = db.get(User, draft.agent_id) or user
    payload = build_render_payload(draft, agent)
    return HTMLResponse(render_html(payload, output_type))


@router.post("/api/quotes/{quote_id}/generate")
def generate_quote(
    quote_id: int,
    request_data: GenerationRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    quote = _get_quote_or_404(db, quote_id)
    draft = request_data.draft
    draft.quote_number = quote.quote_number
    agent = db.get(User, draft.agent_id)
    validation = validate_quote(draft, agent)
    if validation.errors:
        return JSONResponse(
            {"ok": False, "reason": "validation", **validation.model_dump()}, status_code=422
        )
    if validation.warnings and not request_data.acknowledge_warnings:
        return JSONResponse(
            {"ok": False, "reason": "warnings_require_acknowledgement", **validation.model_dump()},
            status_code=409,
        )
    try:
        version = create_version(
            db,
            quote,
            draft,
            user,
            [item.model_dump() for item in validation.warnings],
            request_data.change_note,
        )
    except RenderingUnavailable as exc:
        db.rollback()
        return JSONResponse({"ok": False, "reason": "renderer_unavailable", "message": str(exc)}, status_code=503)
    return {"ok": True, "version": version.version_number, "detail_url": f"/quotes/{quote.id}"}


@router.post("/api/quotes/{quote_id}/copy")
def copy_quote_api(
    quote_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    source = _get_quote_or_404(db, quote_id)
    quote = copy_quote(db, source, user)
    return RedirectResponse(f"/quotes/{quote.id}/edit", status_code=303)


@router.post("/api/quotes/{quote_id}/archive")
def archive_quote(
    quote_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    quote = _get_quote_or_404(db, quote_id)
    quote.status = "Archived"
    quote.archived_at = datetime.utcnow()
    record_event(db, user.id, "archive", quote.id)
    db.commit()
    return RedirectResponse("/", status_code=303)


@router.get("/files/{file_id}/download")
def download_file(
    file_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    generated_file = db.get(GeneratedFile, file_id)
    if generated_file is None or generated_file.generation_status != "completed":
        raise HTTPException(status_code=404, detail="File not found")
    allowed_root = get_settings().generated_files_dir.resolve()
    try:
        path = resolve_verified_file(generated_file, allowed_root)
    except FileIntegrityError:
        raise HTTPException(status_code=409, detail="File integrity check failed") from None
    if path is None:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=generated_file.file_name)
