from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Quote, User
from app.schemas.quote import QuoteDraft
from app.services.audit_service import record_event
from app.services.quote_number_service import next_quote_number


def default_draft(user: User, quote_number: str) -> QuoteDraft:
    today = date.today()
    return QuoteDraft.model_validate(
        {
            "quote_number": quote_number,
            "locale": "zh-TW",
            "currency": "USD",
            "customer": {"name": ""},
            "policy": {
                "carrier": "",
                "term_months": 6,
                "quote_date": today.isoformat(),
                "expiration_date": (today + timedelta(days=10)).isoformat(),
                "vehicle_summary": "",
                "vehicle_count": 1,
                "driver_count": 1,
                "garaging_zip": "",
            },
            "coverages": [
                {"code": "bodily_injury", "value": "$50,000 / $100,000", "sort_order": 10},
                {"code": "property_damage", "value": "$100,000", "sort_order": 20},
                {"code": "collision_deductible", "value": "$1,000", "sort_order": 30},
                {"code": "comprehensive_deductible", "value": "$500", "sort_order": 40},
            ],
            "plans": [
                {"plan_code": "auto_only", "premium_total": None, "sort_order": 10},
                {"plan_code": "auto_renters", "premium_total": None, "recommended": True, "sort_order": 20},
            ],
            "agent_id": user.id,
            "customer_facing_note": "",
            "internal_note": "",
        }
    )


def create_quote(db: Session, user: User) -> Quote:
    quote_number = next_quote_number(db)
    draft = default_draft(user, quote_number)
    quote = Quote(
        quote_number=quote_number,
        customer_name="",
        status="Draft",
        owner_user_id=user.id,
        current_draft_json=draft.model_dump(mode="json"),
        quote_date=draft.policy.quote_date,
        expiration_date=draft.policy.expiration_date,
    )
    db.add(quote)
    db.flush()
    record_event(db, user.id, "create", quote_id=quote.id)
    db.commit()
    return quote


def save_draft(db: Session, quote: Quote, draft: QuoteDraft, user: User) -> Quote:
    draft.quote_number = quote.quote_number
    quote.current_draft_json = draft.model_dump(mode="json")
    quote.customer_name = draft.customer.name.strip()
    quote.quote_date = draft.policy.quote_date
    quote.expiration_date = draft.policy.expiration_date
    quote.updated_at = datetime.utcnow()
    record_event(db, user.id, "update_draft", quote_id=quote.id)
    db.commit()
    return quote


def copy_quote(db: Session, source: Quote, user: User) -> Quote:
    quote_number = next_quote_number(db)
    copied = deepcopy(source.current_draft_json)
    copied["quote_number"] = quote_number
    copied["customer"]["name"] = ""
    copied["customer_facing_note"] = ""
    copied["internal_note"] = ""
    copied["policy"]["quote_date"] = date.today().isoformat()
    copied["policy"]["expiration_date"] = (date.today() + timedelta(days=10)).isoformat()
    for plan in copied.get("plans", []):
        plan["premium_total"] = None
    copied["agent_id"] = user.id
    draft = QuoteDraft.model_validate(copied)
    quote = Quote(
        quote_number=quote_number,
        customer_name="",
        status="Draft",
        owner_user_id=user.id,
        current_draft_json=draft.model_dump(mode="json"),
        latest_version_number=0,
        copied_from_quote_id=source.id,
        quote_date=draft.policy.quote_date,
        expiration_date=draft.policy.expiration_date,
    )
    db.add(quote)
    db.flush()
    record_event(db, user.id, "copy", quote_id=quote.id, metadata={"copied_from_quote_id": source.id})
    db.commit()
    return quote

