from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description='Verify all three localized PNG/PDF outputs with fictional data.')
    parser.add_argument('--artifacts-dir', type=Path, help='Optionally retain fictional outputs for visual review')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='quote-builder-verification-') as temporary:
        root = Path(temporary)
        os.environ['DATABASE_URL'] = f"sqlite:///{(root / 'verification.db').as_posix()}"
        os.environ['GENERATED_FILES_DIR'] = str(root / 'generated')
        os.environ['GEMINI_API_KEY'] = ''

        from app.database import Base, SessionLocal, engine
        from app.models import GeneratedFile, User
        from app.services.auth_service import hash_password
        from app.services.quote_service import create_quote
        from app.services.validation_service import validate_quote
        from app.services.version_service import create_version
        from app.schemas.quote import QuoteDraft

        try:
            Base.metadata.create_all(engine)
            with SessionLocal() as db:
                user = User(
                    username='verification-agent',
                    password_hash=hash_password('temporary-password'),
                    display_name='Verification Agent',
                    chinese_name='測試專員',
                    email='verification@example.com',
                    phone='(202) 555-0100',
                    role='agent',
                    active=True,
                )
                db.add(user)
                db.commit()
                quote = create_quote(db, user)
                for locale in ('zh-TW', 'zh-CN', 'en-US'):
                    draft = dict(quote.current_draft_json)
                    draft['locale'] = locale
                    draft['customer']['name'] = 'Fictional Sample Customer'
                    draft['policy']['carrier'] = 'Fictional Demo Carrier'
                    draft['policy']['vehicle_summary'] = '2024 Demo Vehicle'
                    draft['plans'][0]['premium_total'] = '1200.00'
                    draft['plans'][1]['premium_total'] = '1100.00'
                    validated_draft = QuoteDraft.model_validate(draft)
                    validation = validate_quote(validated_draft, user)
                    assert not validation.errors
                    version = create_version(
                        db, quote, validated_draft, user,
                        [warning.model_dump() for warning in validation.warnings],
                        'Automated generation verification',
                    )
                    files = list(db.query(GeneratedFile).filter_by(quote_version_id=version.id))
                    assert {item.file_type for item in files} == {'mobile_png', 'pdf'}
                    pdf = next(item for item in files if item.file_type == 'pdf')
                    page_count = len(PdfReader(pdf.file_path).pages)
                    assert 1 <= page_count <= 2
                    assert version.quote_snapshot_json['internal_note'] == ''
                    assert 'internal_note' not in str(version.render_payload_json)
                    assert version.render_payload_json['assets'] == {'logo': '', 'qr_code': ''}
                    if args.artifacts_dir:
                        args.artifacts_dir.mkdir(parents=True, exist_ok=True)
                        for item in files:
                            shutil.copyfile(item.file_path, args.artifacts_dir / f'{locale}-{item.file_type}{Path(item.file_path).suffix}')
                    print(f'{locale}: generation passed, 2 files, PDF pages={page_count}')
        finally:
            # Dispose connections even on failure so temporary SQLite files unlock on Windows.
            engine.dispose()


if __name__ == '__main__':
    main()
