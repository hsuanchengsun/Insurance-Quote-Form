from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.quote import QuoteDraft
from app.services.preset_service import get_preset
from app.services.pricing_service import calculate_savings, format_currency
from app.services.translation_service import get_catalog, translate


STATIC_IMAGES_DIR = Path(__file__).resolve().parent.parent / "static" / "images"


@lru_cache
def _image_data_uri(path_text: str) -> str:
    path = Path(path_text)
    if not path.is_file():
        return ""
    mime_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def _agent_qr_data_uri(agent: object) -> str:
    configured = getattr(agent, "qr_code_path", None)
    if configured:
        configured_path = Path(str(configured))
        if not configured_path.is_absolute() and str(configured).startswith("/static/images/"):
            configured_path = STATIC_IMAGES_DIR / configured_path.name
        value = _image_data_uri(str(configured_path))
        if value:
            return value
    return ""


def _period_label(locale: str, period: str) -> str:
    key = f"period.{period}"
    catalog = get_catalog(locale)
    return catalog.get(key, period.replace("_", " "))


def build_render_payload(draft: QuoteDraft, agent: object, version_number: int | None = None) -> dict[str, Any]:
    locale = str(draft.locale)
    catalog = get_catalog(locale)
    coverage_payload: list[dict[str, Any]] = []
    for item in sorted(draft.coverages, key=lambda value: value.sort_order):
        preset = get_preset(item.code)
        label = item.custom_label or translate(locale, f"coverage.{item.code}.label")
        description = item.custom_description or translate(locale, f"coverage.{item.code}.help")
        example = catalog.get(f"coverage.{item.code}.example", "")
        coverage_payload.append(
            {
                "code": item.code,
                "label": label,
                "description": description,
                "example": example,
                "value": item.value,
                "sort_order": item.sort_order,
                "is_custom_value": bool(preset and item.value not in preset.get("values", [])),
            }
        )

    plan_payload: list[dict[str, Any]] = []
    for item in sorted(draft.plans, key=lambda value: value.sort_order):
        plan_payload.append(
            {
                "plan_code": item.plan_code,
                "display_name": item.display_name or catalog.get(f"plan.{item.plan_code}", item.plan_code),
                "premium_total": str(item.premium_total) if item.premium_total is not None else None,
                "premium_formatted": format_currency(item.premium_total, draft.currency),
                "premium_period": item.premium_period,
                "period_label": _period_label(locale, item.premium_period),
                "recommended": item.recommended,
                "short_note": item.short_note,
            }
        )

    savings = calculate_savings(draft.plans)
    if savings:
        savings["amount_formatted"] = format_currency(savings["amount"], draft.currency)

    display_name = getattr(agent, "chinese_name", None) if locale.startswith("zh-") else None
    return {
        "schema_version": "1.0",
        "template_mobile_version": "neutral-v3",
        "template_pdf_version": "neutral-v3",
        "locale": locale,
        "assets": {
            "logo": "",
            "qr_code": _agent_qr_data_uri(agent),
        },
        "labels": catalog,
        "quote": {
            "quote_number": draft.quote_number,
            "display_number": f"{draft.quote_number}-V{version_number}" if version_number else draft.quote_number,
            "currency": draft.currency,
            "customer_name": draft.customer.name,
            "customer_facing_note": draft.customer_facing_note,
        },
        "policy": {
            "carrier": draft.policy.carrier,
            "term_months": draft.policy.term_months,
            "quote_date": draft.policy.quote_date.isoformat(),
            "expiration_date": draft.policy.expiration_date.isoformat(),
            "vehicle_summary": draft.policy.vehicle_summary,
            "vehicle_count": draft.policy.vehicle_count,
            "driver_count": draft.policy.driver_count,
        },
        "coverages": coverage_payload,
        "plans": plan_payload,
        "savings": savings,
        "show_renters_benefits": any(item.plan_code == "auto_renters" for item in draft.plans),
        "renters_benefits": [
            catalog["renters.benefit.personal_property"],
            catalog["renters.benefit.liability"],
            catalog["renters.benefit.additional_living"],
        ],
        "agent": {
            "display_name": display_name or getattr(agent, "display_name", ""),
            "phone": getattr(agent, "phone", ""),
            "email": getattr(agent, "email", ""),
            "license_number": getattr(agent, "license_number", ""),
            "office_address": getattr(agent, "office_address", ""),
            "qr_code_path": getattr(agent, "qr_code_path", None),
        },
        "disclaimer": catalog["quote.disclaimer"],
    }
