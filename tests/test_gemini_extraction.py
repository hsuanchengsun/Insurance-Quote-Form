from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.schemas.quote import QuoteLocale
from app.services.gemini_service import (
    GeminiExtractionError,
    clean_json_text,
    extract_quote_from_pdf,
    map_extraction_to_draft,
    parse_date_safe,
    parse_decimal_safe,
)


def test_clean_json_text():
    assert clean_json_text('{"a": 1}') == '{"a": 1}'
    assert clean_json_text('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert clean_json_text('```\n{"a": 1}\n```') == '{"a": 1}'


def test_parse_date_safe():
    today = date(2026, 8, 10)
    assert parse_date_safe("2026-08-15", today) == date(2026, 8, 15)
    assert parse_date_safe("08/15/2026", today) == date(2026, 8, 15)
    assert parse_date_safe("invalid-date", today) == today
    assert parse_date_safe(None, today) == today


def test_parse_decimal_safe():
    assert parse_decimal_safe("1135.69") == Decimal("1135.69")
    assert parse_decimal_safe("$1,135.69") == Decimal("1135.69")
    assert parse_decimal_safe(1085) == Decimal("1085.00")
    assert parse_decimal_safe(None) is None
    assert parse_decimal_safe("invalid") is None


def test_map_extraction_to_draft_full():
    raw_data = {
        "customer_name": "David Wang",
        "carrier_name": "Mercury Insurance",
        "term_months": 6,
        "quote_date": "2026-08-10",
        "expiration_date": "2026-08-25",
        "vehicle_summary": "2024 Tesla Model Y",
        "vehicle_count": 1,
        "driver_count": 2,
        "garaging_zip": "91770",
        "coverages": [
            {
                "standard_code": "bodily_injury",
                "name_in_pdf": "Bodily Injury",
                "value": "$100,000 / $300,000",
            },
            {
                "standard_code": "property_damage",
                "name_in_pdf": "Property Damage",
                "value": "$100,000",
            },
            {
                "standard_code": "collision_deductible",
                "name_in_pdf": "Collision Deductible",
                "value": "$1,000",
            },
            {
                "standard_code": "custom",
                "name_in_pdf": "Pet Injury Protection",
                "value": "$1,000",
                "custom_label": "寵物傷害保障",
            },
        ],
        "plans": [
            {
                "plan_code": "auto_only",
                "display_name": "Auto Only",
                "premium_total": "1250.50",
                "premium_period": "6_month_policy",
                "recommended": False,
            },
            {
                "plan_code": "auto_renters",
                "display_name": "Auto + Renters",
                "premium_total": "1190.00",
                "premium_period": "6_month_policy",
                "recommended": True,
            },
        ],
        "notes": "Includes good driver discount",
    }

    draft = map_extraction_to_draft(
        raw_data, user_id=1, quote_number="AQ-20260810-0001", locale=QuoteLocale.ZH_TW
    )

    assert draft.customer.name == "David Wang"
    assert draft.policy.carrier == "Mercury Insurance"
    assert draft.policy.term_months == 6
    assert draft.policy.quote_date == date(2026, 8, 10)
    assert draft.policy.expiration_date == date(2026, 8, 25)
    assert draft.policy.vehicle_summary == "2024 Tesla Model Y"
    assert draft.policy.garaging_zip == "91770"

    assert len(draft.coverages) == 4
    assert draft.coverages[0].code == "bodily_injury"
    assert draft.coverages[0].value == "$100,000 / $300,000"
    assert draft.coverages[3].code == "custom_4"
    assert draft.coverages[3].custom_label == "寵物傷害保障"

    assert len(draft.plans) == 2
    assert draft.plans[0].premium_total == Decimal("1250.50")
    assert draft.plans[1].premium_total == Decimal("1190.00")
    assert draft.plans[1].recommended is True
    assert "Mercury Insurance" in draft.internal_note


def test_map_extraction_handles_missing_dates_and_coverages():
    raw_data = {
        "customer_name": "Alice Smith",
        "carrier_name": "Progressive",
        "coverages": [],
        "plans": [
            {
                "plan_code": "auto_only",
                "premium_total": "$980.00",
            }
        ],
    }

    draft = map_extraction_to_draft(
        raw_data, user_id=2, quote_number="AQ-20260810-0002"
    )

    assert draft.customer.name == "Alice Smith"
    assert draft.policy.expiration_date == draft.policy.quote_date + timedelta(days=10)
    # Default 4 coverages were seeded
    assert len(draft.coverages) == 4
    assert draft.coverages[0].code == "bodily_injury"
    # Added auto_renters plan
    assert len(draft.plans) == 2
    assert draft.plans[0].premium_total == Decimal("980.00")
    assert draft.plans[1].plan_code == "auto_renters"


def test_missing_gemini_api_key_raises_user_friendly_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with pytest.raises(GeminiExtractionError) as exc_info:
        extract_quote_from_pdf(b"%PDF-1.4 dummy", user_id=1, quote_number="AQ-001", api_key="")
    assert "GEMINI_API_KEY" in str(exc_info.value)


def test_fallback_cascade_handles_404_and_succeeds():
    from unittest.mock import MagicMock, patch
    from app.services.gemini_service import extract_raw_json_from_gemini

    # Mock first model returns 404 (retired), second model returns valid 200 JSON
    resp_404 = MagicMock(status_code=404, text="Model no longer available")
    resp_200 = MagicMock(
        status_code=200,
        json=lambda: {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": '{"customer_name": "Test User", "carrier_name": "Test"}'}]
                    }
                }
            ]
        },
    )

    with patch("httpx.Client.post", side_effect=[resp_404, resp_200]):
        result = extract_raw_json_from_gemini(b"%PDF dummy", api_key="test-key", model="gemini-3.7-flash")
        assert result["customer_name"] == "Test User"

