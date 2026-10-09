from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from scripts.prepare_public_release import (
    PublicationError, ROOT_FILES, SOURCE_DIRS, build_release, collect_files, scan_files,
)


def minimal_project(root: Path) -> None:
    for name in ROOT_FILES:
        (root / name).write_text('fictional source\n', encoding='utf-8')
    for name in SOURCE_DIRS:
        (root / name).mkdir()
    (root / 'app' / 'main.py').write_text('print("demo")\n', encoding='utf-8')


def test_export_excludes_runtime_data_and_verifies_archive(tmp_path):
    minimal_project(tmp_path)
    for directory, filename in [('generated', 'customer.pdf'), ('uploads', 'policy.pdf'),
                                ('.private', 'private.txt'), ('.antigravity', 'rules')]:
        (tmp_path / directory).mkdir()
        (tmp_path / directory / filename).write_bytes(b'PRIVATE DATA')
    (tmp_path / '.env').write_text('PRIVATE KEY', encoding='utf-8')
    (tmp_path / 'quote_builder.db').write_bytes(b'PRIVATE DATABASE')
    (tmp_path / 'logo.png').write_bytes(b'PRIVATE IMAGE')
    files = collect_files(tmp_path)
    assert '.env' not in files
    assert 'quote_builder.db' not in files
    assert 'logo.png' not in files
    assert not any('PRIVATE' in data.decode() for data in files.values())
    destination, archive = build_release(tmp_path, files, 'demo-release')
    manifest = json.loads((destination / 'PUBLICATION_MANIFEST.json').read_text())
    assert {entry['path'] for entry in manifest['files']} == set(files)
    with zipfile.ZipFile(archive) as zipped:
        assert len(zipped.namelist()) == len(files) + 1
        assert zipped.read('demo-release/generated/.gitkeep') == b''
    with pytest.raises(PublicationError):
        build_release(tmp_path, files, 'demo-release')


def test_unexpected_binary_in_source_fails_closed(tmp_path):
    minimal_project(tmp_path)
    (tmp_path / 'app' / 'customer.pdf').write_bytes(b'PRIVATE')
    with pytest.raises(PublicationError, match='unexpected file'):
        collect_files(tmp_path)


def test_scan_hides_values_and_handles_short_identity_terms():
    key = 'AIza' + 'A' * 35
    email = 'user@' + 'private.invalid'
    files = {'app/main.py': f'raise Exception("demo")\n{key}\nPRIVATECO\n{email}\n'.encode()}
    findings = scan_files(files, ['PRIVATECO'])
    assert any('excluded identity' in item for item in findings)
    assert any('Google API credential' in item for item in findings)
    assert any('non-example email address' in item for item in findings)
    assert key not in '\n'.join(findings)
    assert scan_files({'x.py': b'raise RuntimeError()'}, ['RAI']) == []


def test_scan_checks_private_credentials_even_without_known_prefix():
    credential = 'synthetic-local-secret-value'
    assert scan_files({'config.py': credential.encode()}, credentials=[credential]) == [
        'config.py:1: local credential value'
    ]
