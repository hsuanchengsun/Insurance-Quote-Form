from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models import QuoteSequence


def next_quote_number(db: Session, today: date | None = None) -> str:
    current_date = today or date.today()
    date_key = current_date.strftime("%Y%m%d")
    sequence = db.get(QuoteSequence, date_key)
    if sequence is None:
        sequence = QuoteSequence(date_key=date_key, next_value=2)
        db.add(sequence)
        value = 1
    else:
        value = sequence.next_value
        sequence.next_value += 1
    db.flush()
    return f"AQ-{date_key}-{value:04d}"

