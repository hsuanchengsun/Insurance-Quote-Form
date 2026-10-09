from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QuoteVersion(Base):
    __tablename__ = "quote_versions"
    __table_args__ = (UniqueConstraint("quote_id", "version_number", name="uq_quote_version_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    locale: Mapped[str] = mapped_column(String(10))
    quote_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    render_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    template_mobile_version: Mapped[str] = mapped_column(String(30))
    template_pdf_version: Mapped[str] = mapped_column(String(30))
    version_status: Mapped[str] = mapped_column(String(30), default="current")
    warning_acknowledgements_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    quote = relationship("Quote", back_populates="versions")
    generated_files = relationship("GeneratedFile", back_populates="quote_version")

