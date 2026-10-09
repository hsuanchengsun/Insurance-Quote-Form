# Security and privacy

This project is a local development demo. The included account and fallback session secret are publicly documented examples. Keep the server bound to `127.0.0.1`; public hosting requires separate security work, account management, CSRF protection, request limits, and HTTPS configuration. Demo seeding is disabled outside `APP_ENV=development`.

Set your own random `SECRET_KEY`. Store credentials in local environment variables or an ignored `.env`. Keep databases, uploaded PDFs, generated outputs, QR codes, and logs private. Do not mount generated outputs as public static files.

Optional Gemini extraction sends the entire PDF to Google's API. Manual input does not require an AI provider. Confirm you are authorized to share a PDF before using extraction, and verify the resulting draft.

For a vulnerability, use the repository's private GitHub security reporting option if enabled. If unavailable, open an issue requesting a private contact channel without including an exploit, credentials, customer data, or sensitive attachments. Maintainers should enable private vulnerability reporting before inviting reports.

If a credential is accidentally published, revoke or rotate it at its provider and remove it from all Git history. Removing it in a later commit does not remove the original exposure.
