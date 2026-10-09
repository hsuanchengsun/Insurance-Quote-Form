# Insurance Quote Builder

A local insurance quote workspace built with FastAPI, SQLAlchemy, Jinja2, and Playwright. Enter quote details manually or optionally extract them from a PDF with Google Gemini, then create Traditional Chinese, Simplified Chinese, or English PNG/PDF summaries from the same data.

This repository uses neutral branding and fictional demo records. It is a development demo; coverage descriptions and prices are examples that need review before practical use.

## Features

- Quote drafts, search, copying, archiving, and SQLite persistence.
- Coverage presets, custom limits, up to three plans, and Decimal savings calculations.
- Localized output in `zh-TW`, `zh-CN`, and `en-US` (the editor UI is Traditional Chinese).
- Immutable version snapshots, validation errors/warnings, and private file downloads with SHA-256 verification.
- Playwright mobile PNG and US Letter PDF output.
- Optional Gemini PDF extraction; manual editing and rendering work without an API key.

## Quick start

Use Python 3.10 or later. On Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
python -m alembic upgrade head
python scripts/seed_demo.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8030
```

On macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
python -m alembic upgrade head
python scripts/seed_demo.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8030
```

Open [localhost:8030](http://127.0.0.1:8030). The fictional local demo account is **agent / demo1234**. `seed_demo.py` is intended for a fresh development database. On Windows, `install_demo.cmd` installs the environment and `start_demo.cmd` runs migrations, seeding, diagnostics, and the local server.

Before enabling login, set a random `SECRET_KEY` in your local `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Explicit environment variables take precedence over `.env`. All SQLite databases, uploaded files, generated outputs, credentials, and local archives are excluded from version control and the publication package.

## Optional PDF extraction

Set `GEMINI_API_KEY` in your local `.env` to enable extraction. `GEMINI_MODEL` is configurable; check the [official Gemini model documentation](https://ai.google.dev/gemini-api/docs/models) for model availability in your account.

**PDF extraction sends the uploaded PDF to Google's Gemini API.** Use fictional or authorized data and review extracted details before creating output. The automated tests mock extraction and require no API key or external AI requests.

## Validation

```bash
python -m pytest -q
python scripts/verify_generation.py
```

The generation check uses a temporary database and temporary output directory. It verifies PNG/PDF creation, PDF page count, version snapshots, and private-note isolation. With a fresh demo server running, `python scripts/smoke_browser.py` checks login, editing, and localized previews. Set `BASE_URL` if using another local port.

Additional local utilities:

- `scripts/render_samples.py`: render three languages from the first local quote into `generated/samples/`; these outputs are private and excluded.
- `scripts/check_environment.py`: inspect renderer readiness and local file metadata.
- `scripts/repair_generated_files.py`: inspect existing file hashes; `--apply` repairs files with local backups.

## Repository structure

```text
app/          Models, schemas, services, routes, translations, templates, CSS/JS
migrations/   Alembic schema migrations
scripts/      Demo, rendering, diagnostics, and publication utilities
tests/        Unit and API tests with fictional data
docs/         Architecture and publication instructions
.github/      CI workflow
```

## Public release

```bash
python scripts/prepare_public_release.py --check
python scripts/prepare_public_release.py
```

The second command creates a new source-only folder and ZIP under `release/`, with a SHA-256 file manifest. Upload only that prepared source folder. See [publication instructions](docs/PUBLISHING.md) for Git/GitHub steps and limits of the automated scan.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Code is released under the [MIT License](LICENSE), copyright 2026 Quote Builder contributors.

## 繁體中文說明

這是一套可在本機執行的保險報價展示工具，支援人工輸入、選用 Gemini 解析 PDF，以及產出繁體中文、簡體中文、英文的手機長圖與 PDF。專案採用中性視覺與虛構範例，沒有附帶客戶資料庫、實際報價、聯絡 QR Code 或 API 金鑰。

照上方步驟建立 Python 環境、安裝 Chromium、複製 `.env.example`、執行 migration 與 seed，即可用 `agent / demo1234` 登入本機 Demo。Gemini 為選用功能；啟用後，上傳 PDF 會傳送至 Google API。免責文字與保障說明均為展示範例，實際使用前須自行核對。

公開上傳請使用 `prepare_public_release.py` 產生的乾淨資料夾；完整步驟見 [公開發布說明](docs/PUBLISHING.md)。
