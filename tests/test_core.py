from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import hashlib
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import QuoteVersion, User
from app.schemas.quote import QuoteDraft
from app.services.auth_service import create_session_token, hash_password, read_session_token, verify_password
from app.services.file_service import FileIntegrityError, resolve_verified_file
from app.services.pricing_service import calculate_savings
from app.services.quote_service import copy_quote, create_quote, save_draft
from app.services.render_payload_service import build_render_payload
from app.services.rendering_service import render_html
from app.services.translation_service import assert_catalog_completeness, get_catalog
from app.services.validation_service import validate_quote
from app.services.version_service import create_version


@dataclass
class AgentStub:
    id: int = 1
    display_name: str = "Demo Agent"
    chinese_name: str = "範例專員"
    phone: str = "(202) 555-0100"
    email: str = "agent@example.com"
    license_number: str = "DEMO-NOT-A-LICENSE"
    office_address: str = "Fictional Demo Office"
    qr_code_path: str | None = None


def make_draft(locale: str = "zh-TW") -> QuoteDraft:
    today = date(2026, 8, 10)
    return QuoteDraft.model_validate(
        {
            "quote_number": "AQ-20260810-0001",
            "locale": locale,
            "currency": "USD",
            "customer": {"name": "Sample Customer"},
            "policy": {
                "carrier": "Sample Carrier",
                "term_months": 6,
                "quote_date": today.isoformat(),
                "expiration_date": (today + timedelta(days=10)).isoformat(),
                "vehicle_summary": "2023 Toyota RAV4",
                "vehicle_count": 1,
                "driver_count": 2,
            },
            "coverages": [
                {"code": "bodily_injury", "value": "$50,000 / $100,000", "sort_order": 10},
                {"code": "collision_deductible", "value": "$1,000", "sort_order": 20},
            ],
            "plans": [
                {"plan_code": "auto_only", "premium_total": "1135.69", "sort_order": 10},
                {
                    "plan_code": "auto_renters",
                    "premium_total": "1085.02",
                    "recommended": True,
                    "sort_order": 20,
                },
            ],
            "agent_id": 1,
            "customer_facing_note": "Thank you",
            "internal_note": "Never show this secret note",
        }
    )


def test_translation_catalogs_have_identical_keys():
    assert_catalog_completeness()
    assert get_catalog("zh-TW")["brand.name"] == "Quote Builder"


def test_decimal_savings_is_exact():
    result = calculate_savings(make_draft().plans)
    assert result == {"amount": "50.67", "percentage": "4.5", "positive": True}
    assert isinstance(make_draft().plans[0].premium_total, Decimal)


def test_validation_distinguishes_errors_and_warnings():
    draft = make_draft()
    draft.customer.name = ""
    draft.policy.expiration_date = draft.policy.quote_date + timedelta(days=60)
    result = validate_quote(draft, AgentStub())
    assert any(issue.code == "customer_required" for issue in result.errors)
    assert any(issue.code == "long_validity" for issue in result.warnings)
    assert not result.can_generate


def test_render_payload_is_localized_and_excludes_internal_note():
    payload = build_render_payload(make_draft("zh-TW"), AgentStub(), version_number=1)
    serialized = str(payload)
    assert payload["labels"]["brand.name"] == "Quote Builder"
    assert "Never show this secret note" not in serialized
    assert "internal_note" not in serialized
    assert payload["savings"]["amount_formatted"] == "$50.67"
    assert payload["assets"]["logo"] == ""
    assert payload["assets"]["qr_code"] == ""
    assert "visible_mobile" not in str(payload["coverages"])
    assert "visible_pdf" not in str(payload["coverages"])


def test_output_escapes_customer_text_and_has_no_payment_section():
    draft = make_draft()
    draft.customer.name = "<script>alert('x')</script>"
    html = render_html(build_render_payload(draft, AgentStub()), "mobile_png")
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "installment" not in html.lower()
    assert "down payment" not in html.lower()
    pdf_html = render_html(build_render_payload(make_draft(), AgentStub()), "pdf")
    assert "Thank you" in pdf_html


def test_mobile_and_pdf_include_the_same_coverages():
    payload = build_render_payload(make_draft(), AgentStub())
    mobile_html = render_html(payload, "mobile_png")
    pdf_html = render_html(payload, "pdf")
    for coverage in payload["coverages"]:
        assert coverage["label"] in mobile_html
        assert coverage["label"] in pdf_html


def test_legacy_version_payload_without_brand_assets_still_renders():
    payload = build_render_payload(make_draft(), AgentStub())
    payload.pop("assets")
    assert payload["quote"]["quote_number"] in render_html(payload, "mobile_png")
    assert payload["quote"]["quote_number"] in render_html(payload, "pdf")


def test_output_omits_unconfigured_qr_and_keeps_explicit_custom_qr(tmp_path):
    for output in ("mobile_png", "pdf"):
        html = render_html(build_render_payload(make_draft(), AgentStub()), output)
        assert 'class="qr-image"' not in html
        assert '<img src=""' not in html
    # A synthetic local file tests opt-in asset embedding without bundled branding.
    qr = tmp_path / 'demo.png'
    qr.write_bytes(b'fictional-image-content')
    agent = AgentStub(qr_code_path=str(qr))
    payload = build_render_payload(make_draft(), agent)
    assert payload['assets']['qr_code'].startswith('data:image/png;base64,')
    assert 'class="qr-image"' in render_html(payload, 'mobile_png')


def test_password_and_session_round_trip():
    encoded = hash_password("correct horse")
    assert verify_password("correct horse", encoded)
    assert not verify_password("wrong", encoded)
    token = create_session_token(42, "test-secret")
    assert read_session_token(token, "test-secret") == 42
    assert read_session_token(token, "other-secret") is None


def test_generated_file_path_and_hash_are_verified(tmp_path):
    generated = tmp_path / "generated"
    generated.mkdir()
    output = generated / "quote.pdf"
    output.write_bytes(b"expected content")
    record = SimpleNamespace(
        file_path=str(output), content_hash=hashlib.sha256(output.read_bytes()).hexdigest()
    )
    assert resolve_verified_file(record, generated) == output.resolve()
    output.write_bytes(b"modified")
    try:
        resolve_verified_file(record, generated)
        assert False, "Modified files must fail integrity verification"
    except FileIntegrityError:
        pass

    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"outside")
    outside_record = SimpleNamespace(
        file_path=str(outside), content_hash=hashlib.sha256(outside.read_bytes()).hexdigest()
    )
    assert resolve_verified_file(outside_record, generated) is None


def test_copy_quote_clears_identity_and_premium():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(
            username="agent",
            password_hash="hash",
            display_name="Agent",
            email="agent@example.com",
            phone="555-0100",
            role="agent",
            active=True,
        )
        db.add(user)
        db.commit()
        source = create_quote(db, user)
        save_draft(db, source, make_draft(), user)
        copied = copy_quote(db, source, user)
        assert copied.copied_from_quote_id == source.id
        assert copied.current_draft_json["customer"]["name"] == ""
        assert all(plan["premium_total"] is None for plan in copied.current_draft_json["plans"])
        assert copied.quote_number != source.quote_number


def test_version_snapshot_is_immutable(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(
            username="agent",
            password_hash="hash",
            display_name="Agent",
            chinese_name="專員",
            email="agent@example.com",
            phone="555-0100",
            role="agent",
            active=True,
        )
        db.add(user)
        db.commit()
        quote = create_quote(db, user)
        draft = make_draft()
        draft.agent_id = user.id
        monkeypatch.setattr("app.services.version_service.generate_output_files", lambda payload, output_dir: [])
        version = create_version(db, quote, draft, user, [])
        original_name = version.quote_snapshot_json["customer"]["name"]
        draft.customer.name = "Changed Later"
        stored = db.get(QuoteVersion, version.id)
        assert stored.quote_snapshot_json["customer"]["name"] == original_name
