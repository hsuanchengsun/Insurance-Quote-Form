from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import Quote, User  # noqa: E402
from app.schemas.quote import QuoteDraft  # noqa: E402
from app.services.auth_service import hash_password  # noqa: E402
from app.services.quote_service import create_quote, save_draft  # noqa: E402


DEMO_USERNAME = "agent"
DEMO_PASSWORD = "demo1234"


def main() -> None:
    if os.getenv("APP_ENV", "development").lower() != "development":
        raise SystemExit("Demo seeding is only available in APP_ENV=development.")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == DEMO_USERNAME))
        if user is None:
            user = User(
                username=DEMO_USERNAME,
                password_hash=hash_password(DEMO_PASSWORD),
                display_name="Demo Agent",
                chinese_name="範例專員",
                email="agent@example.com",
                phone="(202) 555-0100",
                license_number="DEMO-NOT-A-LICENSE",
                office_address="Fictional Demo Office",
                role="agent",
                active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        sample = db.scalar(select(Quote).where(Quote.customer_name == "範例客戶（虛構資料）"))
        if sample is None:
            sample = create_quote(db, user)
            today = date.today()
            draft = QuoteDraft.model_validate(
                {
                    "quote_number": sample.quote_number,
                    "locale": "zh-TW",
                    "currency": "USD",
                    "customer": {"name": "範例客戶（虛構資料）"},
                    "policy": {
                        "carrier": "Fictional Demo Carrier",
                        "term_months": 6,
                        "quote_date": today.isoformat(),
                        "expiration_date": (today + timedelta(days=10)).isoformat(),
                        "vehicle_summary": "2024 Demo Vehicle",
                        "vehicle_count": 1,
                        "driver_count": 2,
                        "garaging_zip": "00000",
                    },
                    "coverages": [
                        {"code": "bodily_injury", "value": "$50,000 / $100,000", "sort_order": 10},
                        {"code": "property_damage", "value": "$100,000", "sort_order": 20},
                        {"code": "uninsured_motorist", "value": "$50,000 / $100,000", "sort_order": 30},
                        {"code": "collision_deductible", "value": "$1,000", "sort_order": 40},
                        {"code": "comprehensive_deductible", "value": "$500", "sort_order": 50},
                        {"code": "rental_reimbursement", "value": "$40/day, up to 30 days", "sort_order": 60},
                        {"code": "roadside_assistance", "value": "Included", "sort_order": 70},
                    ],
                    "plans": [
                        {"plan_code": "auto_only", "premium_total": "1135.69", "premium_period": "6_month_policy", "recommended": False, "sort_order": 10},
                        {"plan_code": "auto_renters", "premium_total": "1085.02", "premium_period": "6_month_policy", "recommended": True, "sort_order": 20},
                    ],
                    "agent_id": user.id,
                    "customer_facing_note": "感謝您讓我們協助比較保障內容，如有疑問請直接聯絡專員。",
                    "internal_note": "Demo only. Never include this text in customer output.",
                }
            )
            save_draft(db, sample, draft, user)

    print("Demo data is ready.")
    print(f"Login: {DEMO_USERNAME} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
