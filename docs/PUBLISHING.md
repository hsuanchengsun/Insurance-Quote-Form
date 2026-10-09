# Preparing a public GitHub repository

Use the generated publication folder as the repository root. The development workspace may contain ignored private data; do not upload or ZIP the entire workspace.

## Build and inspect

From the development workspace:

```bash
python -m pytest -q
python scripts/verify_generation.py
python scripts/prepare_public_release.py --check
python scripts/prepare_public_release.py
```

The tool prints the new folder and ZIP paths. Each build creates a new folder under `release/` and refuses to overwrite an existing one. `PUBLICATION_MANIFEST.json` contains file names, sizes, and SHA-256 hashes without local absolute paths. The ZIP contains the same checked source files.

The export uses an explicit allowlist of source folders, text extensions, and root files. It excludes `.env`, virtual environments, SQLite files, logs, uploads, generated outputs, images, local editor settings, internal planning documents, private archives, and Git history. Unexpected files inside source folders cause a failed check.

The scan checks common credential formats, non-example email addresses, Windows user paths, and configured denied terms. For your private organization-specific terms, create an ignored `.private/publication-deny-terms.txt`, one term per line, or pass repeated `--deny-term` arguments. Local `.env` credential values are compared without printing them. These private rules are deliberately excluded from the publication package.

An automated scan cannot identify every private business rule, personal name, encoded secret, or ownership concern. Review the actual source and manifest before publishing. Re-run the check after any edits. Confirm that all code and assets can be released under MIT.

## Upload with Git

Open a terminal in the printed **source folder**, then:

```bash
git init -b main
git add .
git diff --cached --stat
git diff --cached
git commit -m "Initial public release"
```

On your own GitHub account, create an empty repository (suggested name: `insurance-quote-builder`). Set its visibility to Public when ready. Do not have GitHub generate another README, license, or `.gitignore`. Replace the placeholders below with your own account and repository:

```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

If Git requests an identity, configure your own name and a GitHub no-reply email. Authenticate using your existing GitHub sign-in method. No account, remote URL, token, or personal commit identity is bundled.

Suggested repository description: `A local insurance quote workspace with multilingual PNG/PDF output and optional Gemini PDF extraction.` Suggested topics: `fastapi`, `python`, `insurance`, `playwright`, `pdf`, `jinja2`.

## 中文發布說明

請只上傳工具產生的乾淨資料夾，將它當成新的 repo 根目錄。原開發資料夾可能仍保留本機金鑰、舊資料庫、歷史輸出與私有封存；這些不會進入上傳包。

檢查測試結果與 manifest，閱讀實際程式內容，確認授權後，再到自己的 GitHub 建立空白 repo 並依上方步驟推送。私人排除關鍵字清單不會發布，後續新增素材時應再次掃描。
