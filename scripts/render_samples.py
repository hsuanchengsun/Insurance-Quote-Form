from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Quote, User  # noqa: E402
from app.schemas.quote import QuoteDraft  # noqa: E402
from app.services.render_payload_service import build_render_payload  # noqa: E402
from app.services.rendering_service import generate_output_files  # noqa: E402


def main() -> None:
    with SessionLocal() as db:
        quote = db.scalar(select(Quote).order_by(Quote.id))
        if quote is None:
            raise SystemExit("No sample quote. Run python scripts/seed_demo.py first.")
        draft = QuoteDraft.model_validate(quote.current_draft_json)
        agent = db.get(User, draft.agent_id)
        if agent is None:
            raise SystemExit("Sample quote agent is missing.")
        localized_notes = {
            "zh-TW": "感謝您讓我們協助比較保障內容，如有疑問請直接聯絡專員。",
            "zh-CN": "感谢您让我们协助比较保障内容，如有疑问请直接联系专员。",
            "en-US": "Thank you for letting us help compare your coverage options. Contact your agent with any questions.",
        }
        sample_output_dir = get_settings().generated_files_dir / "samples"
        for locale in ("zh-TW", "zh-CN", "en-US"):
            localized = draft.model_copy(deep=True)
            localized.locale = locale
            localized.customer_facing_note = localized_notes[locale]
            payload = build_render_payload(localized, agent, version_number=1)
            files = generate_output_files(payload, sample_output_dir)
            print(locale, *(item["file_name"] for item in files))


if __name__ == "__main__":
    main()
