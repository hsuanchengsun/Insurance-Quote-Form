from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import GeneratedFile, QuoteVersion  # noqa: E402
from app.services.audit_service import record_event  # noqa: E402
from app.services.rendering_service import generate_output_files  # noqa: E402


def mismatched_files() -> list[GeneratedFile]:
    with SessionLocal() as db:
        results: list[GeneratedFile] = []
        for item in db.scalars(select(GeneratedFile)).all():
            path = Path(item.file_path)
            actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            if actual != item.content_hash:
                db.expunge(item)
                results.append(item)
        return results


def repair() -> int:
    mismatches = mismatched_files()
    if not mismatches:
        print("No generated-file mismatches found.")
        return 0

    settings = get_settings()
    backup_root = settings.generated_files_dir / "recovery-backups" / datetime.now().strftime("%Y%m%d-%H%M%S")
    work_root = settings.generated_files_dir / ".repair-work"
    backup_root.mkdir(parents=True, exist_ok=True)
    work_root.mkdir(parents=True, exist_ok=True)

    version_ids = sorted({item.quote_version_id for item in mismatches})
    try:
        with SessionLocal() as db:
            for version_id in version_ids:
                version = db.get(QuoteVersion, version_id)
                if version is None:
                    raise RuntimeError(f"Missing quote version id={version_id}")
                records = list(
                    db.scalars(select(GeneratedFile).where(GeneratedFile.quote_version_id == version_id)).all()
                )
                for record in records:
                    current = Path(record.file_path)
                    if current.is_file():
                        shutil.copy2(current, backup_root / current.name)

                rendered = generate_output_files(version.render_payload_json, work_root)
                rendered_by_type = {item["file_type"]: item for item in rendered}
                repaired_ids: list[int] = []
                for record in records:
                    new_item = rendered_by_type[record.file_type]
                    source = Path(new_item["file_path"])
                    destination = Path(record.file_path)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                    record.content_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
                    record.file_size_bytes = destination.stat().st_size
                    record.generation_status = "completed"
                    record.error_message = None
                    repaired_ids.append(record.id)
                record_event(
                    db,
                    actor_user_id=version.created_by,
                    action="repair_generated_files",
                    quote_id=version.quote_id,
                    quote_version_id=version.id,
                    metadata={"file_ids": repaired_ids, "backup_directory": str(backup_root)},
                )
            db.commit()
    finally:
        shutil.rmtree(work_root, ignore_errors=True)

    print(f"Repaired {len(mismatches)} file record(s). Backup: {backup_root}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair generated files from immutable version payloads.")
    parser.add_argument("--apply", action="store_true", help="Back up and repair mismatched files.")
    args = parser.parse_args()
    mismatches = mismatched_files()
    if not mismatches:
        print("No generated-file mismatches found.")
        return 0
    for item in mismatches:
        print(f"Mismatch: id={item.id} {item.file_name}")
    if not args.apply:
        print("Run again with --apply to back up and repair from immutable version payloads.")
        return 1
    return repair()


if __name__ == "__main__":
    raise SystemExit(main())

