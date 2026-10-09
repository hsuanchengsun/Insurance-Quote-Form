# Architecture

FastAPI serves a Jinja2 editor with plain JavaScript. SQLAlchemy persists quote drafts, users, immutable quote versions, file metadata, and audit events. Alembic manages schema migrations.

The output pipeline is: validated draft → localized render payload → mobile/PDF Jinja2 templates → Playwright PNG/PDF → private file download. Decimal arithmetic keeps premiums and savings exact. Generated files are checked against stored SHA-256 hashes.

Optional Gemini extraction posts PDF bytes to the Gemini API, maps the returned JSON to a draft, and leaves the result for manual review. It does not determine coverage or calculate an insurer's rate.

Output catalogs live in `app/i18n/`. The UI and output use neutral text branding and a blue palette. No logo or QR code is bundled. A user with an explicitly configured local `qr_code_path` can still render their own QR image; there is no fallback contact destination.

Quote version snapshots preserve their original payloads. A local database created before changing templates may still contain previous branding or personal details. Publication utilities never copy local databases, historical outputs, uploads, or local archives.

The scope is a single local workspace. Payments, signatures, customer login, carrier/CRM integrations, production identity management, and multi-tenancy are outside the demo.
