# Contributing

Use the setup steps in README.md and a fresh local demo database. Open an issue describing the behavior you want to change, then submit a focused pull request with an explanation and relevant validation.

Before submitting:

```bash
python -m pytest -q
python scripts/prepare_public_release.py --check
```

Run `python scripts/verify_generation.py` for changes affecting output rendering or snapshots. Keep the three translation catalogs aligned and verify affected localized output.

Use fictional people, `example.com` email addresses, and synthetic policy details. Never include credentials, company assets, actual quotes, customer PDFs, databases, logs, screenshots of private data, or generated customer files. Do not add real PDFs as test fixtures. Use mocks for external extraction requests.

Code contributions are provided under the repository's MIT License. New third-party assets or dependencies must have documented provenance and compatible terms.
