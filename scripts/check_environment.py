from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def check_renderer() -> list[str]:
    failures: list[str] = []
    expected = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if os.name == "nt" and expected.is_file() and Path(sys.executable).resolve() != expected.resolve():
        failures.append(
            f"Wrong Python: {sys.executable}. Start with start_demo.cmd so the app uses {expected}."
        )
    required_modules = ("fastapi", "sqlalchemy", "jinja2", "dotenv", "playwright")
    missing = [name for name in required_modules if importlib.util.find_spec(name) is None]
    if missing:
        failures.append(
            "Missing Python packages: " + ", ".join(missing) + ". Run install_demo.cmd."
        )
        return failures
    from app.services.rendering_service import renderer_diagnostics

    diagnostics = renderer_diagnostics(launch_browser=True)
    if not diagnostics["ready"]:
        failures.append(str(diagnostics["message"]))
    else:
        print(f"[OK] Renderer: {diagnostics['executable']}")
    return failures


def check_application() -> list[str]:
    from sqlalchemy import select, text

    from app.config import get_settings
    from app.database import SessionLocal
    from app.models import GeneratedFile
    from app.services.translation_service import assert_catalog_completeness

    failures: list[str] = []
    settings = get_settings()
    try:
        assert_catalog_completeness()
        print("[OK] Translation catalogs")
    except Exception as exc:
        failures.append(f"Translation catalogs: {exc}")

    settings.generated_files_dir.mkdir(parents=True, exist_ok=True)
    probe = settings.generated_files_dir / ".write-check"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        print(f"[OK] Generated files directory: {settings.generated_files_dir}")
    except OSError as exc:
        failures.append(f"Generated files directory is not writable: {exc}")

    try:
        with SessionLocal() as db:
            if settings.database_url.startswith("sqlite"):
                integrity = db.execute(text("PRAGMA integrity_check")).scalar()
                if integrity != "ok":
                    failures.append(f"SQLite integrity check returned: {integrity}")
                foreign_key_errors = db.execute(text("PRAGMA foreign_key_check")).all()
                if foreign_key_errors:
                    failures.append(f"SQLite foreign-key errors: {foreign_key_errors}")
            mismatches: list[str] = []
            for item in db.scalars(select(GeneratedFile)).all():
                path = Path(item.file_path)
                if not path.is_file():
                    mismatches.append(f"missing file id={item.id}: {item.file_name}")
                    continue
                actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                if actual_hash != item.content_hash:
                    mismatches.append(f"hash mismatch id={item.id}: {item.file_name}")
            if mismatches:
                failures.append("Generated-file consistency: " + "; ".join(mismatches))
            else:
                print("[OK] Database integrity and generated-file hashes")
    except Exception as exc:
        failures.append(f"Database check failed: {exc}")
    return failures


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Verify the Quote Builder runtime environment.")
    parser.add_argument("--renderer-only", action="store_true")
    args = parser.parse_args()

    print(f"Python: {sys.executable}")
    failures = check_renderer()
    if not args.renderer_only:
        failures.extend(check_application())
    if failures:
        print("\nEnvironment check failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("[OK] Environment ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
