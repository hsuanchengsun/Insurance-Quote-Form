from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GeneratedFile(Base):
    __tablename__ = "generated_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_version_id: Mapped[int] = mapped_column(ForeignKey("quote_versions.id"), index=True)
    file_type: Mapped[str] = mapped_column(String(30))
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(1000))
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    generation_status: Mapped[str] = mapped_column(String(30), default="completed")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    quote_version = relationship("QuoteVersion", back_populates="generated_files")

