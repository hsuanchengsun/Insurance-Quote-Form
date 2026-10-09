from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.schemas.quote import PlanItem


def calculate_savings(plans: list[PlanItem]) -> dict[str, str] | None:
    auto = next((p for p in plans if p.plan_code == "auto_only" and p.premium_total is not None), None)
    bundle = next((p for p in plans if p.plan_code == "auto_renters" and p.premium_total is not None), None)
    if not auto or not bundle or auto.premium_total in (None, Decimal("0")):
        return None
    amount = (auto.premium_total - bundle.premium_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    percentage = ((amount / auto.premium_total) * Decimal("100")).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    return {"amount": str(amount), "percentage": str(percentage), "positive": amount > 0}


def format_currency(value: Decimal | str | None, currency: str = "USD") -> str:
    if value is None:
        return "—"
    amount = Decimal(str(value))
    symbol = "$" if currency == "USD" else f"{currency} "
    return f"{symbol}{amount:,.2f}"

