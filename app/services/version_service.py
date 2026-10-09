from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import GeneratedFile, Quote, QuoteVersion, User
from app.schemas.quote import QuoteDraft
from app.services.audit_service import record_event
from app.services.render_payload_service import build_render_payload
from app.services.rendering_service import generate_output_files


def create_version(
    db: Session,
    quote: Quote,
    draft: QuoteDraft,
    user: User,
    warning_acknowledgements: list[dict],
    change_note: str = "",
) -> QuoteVersion:
    next_version = quote.latest_version_number + 1
    draft.quote_number = quote.quote_number
    payload = build_render_payload(draft, user, version_number=next_version)

    previous_versions = db.scalars(
        select(QuoteVersion).where(QuoteVersion.quote_id == quote.id, QuoteVersion.version_status == "current")
    ).all()
    for previous in previous_versions:
        previous.version_status = "superseded"

    version = QuoteVersion(
        quote_id=quote.id,
        version_number=next_version,
        locale=str(draft.locale),
        quote_snapshot_json=draft.model_dump(mode="json"),
        render_payload_json=payload,
        template_mobile_version=payload["template_mobile_version"],
        template_pdf_version=payload["template_pdf_version"],
        version_status="current",
        warning_acknowledgements_json=warning_acknowledgements,
        change_note=change_note.strip() or None,
        created_by=user.id,
    )
    db.add(version)
    db.flush()

    files = generate_output_files(payload, get_settings().generated_files_dir)
    for item in files:
        db.add(GeneratedFile(quote_version_id=version.id, generated_by=user.id, generation_status="completed", **item))

    quote.current_draft_json = draft.model_dump(mode="json")
    quote.customer_name = draft.customer.name
    quote.quote_date = draft.policy.quote_date
    quote.expiration_date = draft.policy.expiration_date
    quote.latest_version_number = next_version
    quote.status = "Generated"
    record_event(db, user.id, "generate", quote.id, version.id, {"version_number": next_version})
    db.commit()
    return version

