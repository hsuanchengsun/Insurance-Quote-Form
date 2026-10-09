from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    app_env: str
    secret_key: str
    database_url: str
    generated_files_dir: Path
    base_url: str
    session_cookie_name: str
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.7-flash"

    @property
    def secure_cookies(self) -> bool:
        return self.app_env.lower() == "production"


def get_settings() -> Settings:
    # Explicit environment variables must take precedence over local settings.
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    generated = Path(os.getenv("GENERATED_FILES_DIR", "./generated"))
    if not generated.is_absolute():
        generated = PROJECT_ROOT / generated
    raw_api_key = os.getenv("GEMINI_API_KEY", "").strip().strip("'\"").strip()
    raw_model = os.getenv("GEMINI_MODEL", "gemini-3.7-flash").strip().strip("'\"").strip() or "gemini-3.7-flash"
    return Settings(
        app_env=os.getenv("APP_ENV", "development").strip(),
        secret_key=os.getenv("SECRET_KEY", "demo-only-change-before-deployment").strip(),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./quote_builder.db").strip(),
        generated_files_dir=generated.resolve(),
        base_url=os.getenv("BASE_URL", "http://127.0.0.1:8030").strip(),
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "quote_builder_session").strip(),
        gemini_api_key=raw_api_key,
        gemini_model=raw_model,
    )



