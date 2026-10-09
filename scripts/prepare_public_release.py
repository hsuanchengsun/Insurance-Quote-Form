"""Build a checked source-only publication folder using the standard library."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROOT_FILES = (
    '.env.example', '.gitignore', '.gitattributes', 'README.md', 'LICENSE',
    'CONTRIBUTING.md', 'SECURITY.md', 'requirements.txt', 'alembic.ini',
    'install_demo.cmd', 'start_demo.cmd', 'pytest.ini',
)
SOURCE_DIRS = ('app', 'migrations', 'scripts', 'tests', 'docs', '.github')
TEXT_EXTENSIONS = {'.py', '.html', '.css', '.js', '.json', '.mako', '.md', '.yml', '.yaml'}
SKIP_DIRS = {'__pycache__', '.pytest_cache', '.git'}
SECRET_RULES = (
    ('Google API credential', re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b')),
    ('GitHub credential', re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b')),
    ('AWS access credential', re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')),
    ('private key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('embedded image data', re.compile(r'data:image/[^;]+;base64,[A-Za-z0-9+/=]{100,}')),
    ('Windows personal path', re.compile(r'[A-Z]:[\\/]+Users[\\/]+[^\s"\']+', re.I)),
)
EMAIL = re.compile(r'\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b')


class PublicationError(RuntimeError):
    pass


def collect_files(root: Path) -> dict[str, bytes]:
    root = root.resolve()
    files: dict[str, bytes] = {}

    def add(path: Path) -> None:
        relative = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise PublicationError(f'{relative}: symlink or external path is not allowed')
        # Match Git's canonical text blobs so manifest hashes survive staging.
        data = path.read_bytes().replace(b'\r\n', b'\n')
        if len(data) > 1_000_000:
            raise PublicationError(f'{relative}: unexpectedly large source file')
        try:
            data.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise PublicationError(f'{relative}: source must be UTF-8 text') from None
        files[relative] = data

    for name in ROOT_FILES:
        path = root / name
        if not path.is_file():
            raise PublicationError(f'{name}: required publication file is missing')
        add(path)
    for directory in SOURCE_DIRS:
        folder = root / directory
        if folder.is_symlink():
            raise PublicationError(f'{directory}: symlink directory is not allowed')
        if not folder.is_dir():
            raise PublicationError(f'{directory}: required source directory is missing')
        for path in sorted(folder.rglob('*')):
            relative = path.relative_to(root)
            if any(part in SKIP_DIRS for part in relative.parts):
                continue
            if path.is_symlink():
                raise PublicationError(f'{relative.as_posix()}: symlink is not allowed')
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_EXTENSIONS or path.name.startswith('.env'):
                raise PublicationError(f'{relative.as_posix()}: unexpected file in source directory')
            add(path)
    # Keep runtime folders empty; never inspect or copy their existing contents.
    files['generated/.gitkeep'] = b''
    files['uploads/.gitkeep'] = b''
    return dict(sorted(files.items()))


def private_scan_inputs(root: Path) -> tuple[list[str], list[str]]:
    terms: list[str] = []
    path = root / '.private' / 'publication-deny-terms.txt'
    if path.is_file():
        terms = [line.strip() for line in path.read_text(encoding='utf-8-sig').splitlines()
                 if line.strip() and not line.lstrip().startswith('#')]
    credentials: list[str] = []
    env = root / '.env'
    if env.is_file():
        for line in env.read_text(encoding='utf-8-sig').splitlines():
            key, separator, value = line.partition('=')
            if not separator or key.strip() not in {'SECRET_KEY', 'GEMINI_API_KEY'}:
                continue
            value = value.strip().strip('"\'')
            if len(value) >= 12 and not any(marker in value.lower() for marker in
                    ('replace-me', 'your-', 'demo-only', 'example', 'placeholder')):
                credentials.append(value)
    return terms, credentials


def scan_files(files: dict[str, bytes], terms: list[str] | None = None,
               credentials: list[str] | None = None) -> list[str]:
    findings: list[str] = []
    term_rules = []
    for term in terms or []:
        # Short acronyms must not match the middle of ordinary words.
        escaped = re.escape(term)
        pattern = rf'(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])' if term.isascii() and term.isalnum() else escaped
        term_rules.append(re.compile(pattern, re.I))
    for name, data in files.items():
        text = data.decode('utf-8-sig')
        for rule in term_rules:
            if rule.search(name):
                findings.append(f'{name}: excluded identity in file name')
        for line_number, line in enumerate(text.splitlines(), 1):
            labels = {label for label, rule in SECRET_RULES if rule.search(line)}
            if any(rule.search(line) for rule in term_rules):
                labels.add('excluded identity')
            if any(value in line for value in credentials or []):
                labels.add('local credential value')
            for match in EMAIL.finditer(line):
                domain = match.group(1).lower()
                if domain not in {'example.com', 'example.org', 'example.net'} and not domain.endswith('.example'):
                    labels.add('non-example email address')
            # Report locations and categories only; never print matching secrets.
            for label in sorted(labels):
                findings.append(f'{name}:{line_number}: {label}')
    return findings


def build_release(root: Path, files: dict[str, bytes], label: str) -> tuple[Path, Path]:
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', label):
        raise PublicationError('Release name must use letters, digits, hyphens, or underscores')
    releases = root.resolve() / 'release'
    if releases.is_symlink():
        raise PublicationError('Release directory cannot be a symlink')
    destination = releases / label
    archive = releases / f'{label}.zip'
    if destination.exists() or archive.exists():
        raise PublicationError('Release destination exists; choose another --name')
    manifest = {
        'project': 'Insurance Quote Builder',
        'license': 'MIT',
        'files': [{'path': name, 'size_bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                  for name, data in files.items()],
    }
    packaged = dict(files)
    packaged['PUBLICATION_MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    destination.mkdir(parents=True)
    for name, data in packaged.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, data in sorted(packaged.items()):
            zipped.writestr(f'{label}/{name}', data)
    with zipfile.ZipFile(archive) as zipped:
        expected = {f'{label}/{name}' for name in packaged}
        if set(zipped.namelist()) != expected or zipped.testzip() is not None:
            raise PublicationError('ZIP membership or integrity verification failed')
        for name, data in packaged.items():
            if zipped.read(f'{label}/{name}') != data or (destination / name).read_bytes() != data:
                raise PublicationError(f'{name}: exported content verification failed')
    return destination, archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Scan without creating a release')
    parser.add_argument('--name', default=None, help='Unique release folder name')
    parser.add_argument('--deny-term', action='append', default=[], help='Additional private identity to exclude')
    args = parser.parse_args()
    try:
        files = collect_files(PROJECT_ROOT)
        terms, credentials = private_scan_inputs(PROJECT_ROOT)
        findings = scan_files(files, terms + args.deny_term, credentials)
        if findings:
            print('Publication check FAILED. Matching values are intentionally hidden.')
            for finding in findings:
                print(f'  {finding}')
            return 1
        print(f'Publication check passed: {len(files)} source files, {len(terms + args.deny_term)} private identity rules.')
        if not args.check:
            label = args.name or f'insurance-quote-builder-public-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}'
            destination, archive = build_release(PROJECT_ROOT, files, label)
            print(f'Source folder: {destination}')
            print(f'ZIP: {archive}')
            print(f'ZIP SHA-256: {hashlib.sha256(archive.read_bytes()).hexdigest()}')
        return 0
    except (PublicationError, OSError) as exc:
        print(f'Publication check FAILED: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
