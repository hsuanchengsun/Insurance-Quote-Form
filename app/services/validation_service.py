from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from app.schemas.quote import QuoteDraft
from app.schemas.validation import ValidationIssue, ValidationResult
from app.services.preset_service import get_preset


def _issue(level: str, code: str, field: str, message: str) -> ValidationIssue:
    return ValidationIssue(level=level, code=code, field=field, message=message)  # type: ignore[arg-type]


def validate_quote(draft: QuoteDraft, agent: object | None = None) -> ValidationResult:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    if not draft.customer.name.strip():
        errors.append(_issue("error", "customer_required", "customer.name", "Customer name is required."))
    if not draft.policy.carrier.strip():
        errors.append(_issue("error", "carrier_required", "policy.carrier", "Carrier is required."))
    if draft.policy.expiration_date < draft.policy.quote_date:
        errors.append(
            _issue("error", "invalid_expiration", "policy.expiration_date", "Expiration date cannot be before quote date.")
        )
    if draft.policy.expiration_date - draft.policy.quote_date > timedelta(days=45):
        warnings.append(
            _issue("warning", "long_validity", "policy.expiration_date", "Quote validity is longer than 45 days.")
        )

    if not draft.coverages:
        errors.append(_issue("error", "coverage_required", "coverages", "At least one coverage is required."))
    for index, coverage in enumerate(draft.coverages):
        if not coverage.value.strip():
            errors.append(
                _issue("error", "coverage_value_required", f"coverages.{index}.value", "Coverage value is required.")
            )
        preset = get_preset(coverage.code)
        if preset and coverage.value and coverage.value not in preset.get("values", []):
            warnings.append(
                _issue("warning", "custom_coverage_value", f"coverages.{index}.value", "Coverage uses a custom value.")
            )

    if not draft.plans:
        errors.append(_issue("error", "plan_required", "plans", "At least one pricing plan is required."))
    for index, plan in enumerate(draft.plans):
        if plan.premium_total is None:
            errors.append(_issue("error", "premium_required", f"plans.{index}.premium_total", "Premium is required."))
        elif plan.premium_total < Decimal("0"):
            errors.append(_issue("error", "premium_negative", f"plans.{index}.premium_total", "Premium cannot be negative."))

    auto = next((p for p in draft.plans if p.plan_code == "auto_only"), None)
    bundle = next((p for p in draft.plans if p.plan_code == "auto_renters"), None)
    if (
        auto
        and bundle
        and auto.premium_total is not None
        and bundle.premium_total is not None
        and bundle.premium_total >= auto.premium_total
        and bundle.recommended
    ):
        warnings.append(
            _issue("warning", "non_positive_bundle_savings", "plans", "Recommended bundle does not cost less than Auto Only.")
        )

    if agent is None:
        errors.append(_issue("error", "agent_missing", "agent_id", "Agent profile could not be found."))
    else:
        for field in ("display_name", "phone", "email"):
            if not str(getattr(agent, field, "") or "").strip():
                errors.append(_issue("error", f"agent_{field}_required", "agent_id", f"Agent {field} is required."))

    return ValidationResult(errors=errors, warnings=warnings)
