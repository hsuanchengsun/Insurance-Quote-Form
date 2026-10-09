from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

from app.web import templates


class RenderingUnavailable(RuntimeError):
    pass


def renderer_diagnostics(launch_browser: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ready": False,
        "python": sys.executable,
        "package": False,
        "browser": False,
        "message": "",
    }
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        result["message"] = (
            "Playwright 未安裝在目前伺服器使用的 Python。"
            "請改用 start_demo.cmd，或以 .venv\\Scripts\\python.exe 啟動 Uvicorn。"
        )
        return result

    result["package"] = True
    try:
        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
            result["executable"] = str(executable)
            if not executable.is_file():
                result["message"] = (
                    "Playwright 已安裝，但找不到 Chromium。"
                    "請執行 .venv\\Scripts\\playwright.exe install chromium。"
                )
                return result
            if launch_browser:
                browser = playwright.chromium.launch(headless=True)
                browser.close()
            result["browser"] = True
            result["ready"] = True
            result["message"] = "Renderer ready"
            return result
    except Exception as exc:
        result["message"] = (
            "Chromium 無法啟動。請使用 start_demo.cmd 啟動專案，"
            f"並檢查 Playwright 安裝。技術訊息：{exc}"
        )
        return result


def render_html(payload: dict[str, Any], output_type: str) -> str:
    template_name = "mobile/auto_quote_v1.html" if output_type == "mobile_png" else "pdf/auto_quote_v1.html"
    template = templates.env.get_template(template_name)
    return template.render(payload=payload)


def generate_output_files(payload: dict[str, Any], output_dir: Path) -> list[dict[str, Any]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RenderingUnavailable(
            "Playwright 未安裝在目前伺服器使用的 Python。請停止伺服器，"
            "再從專案根目錄執行 start_demo.cmd。"
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = payload["quote"]["display_number"] + "-" + payload["locale"]
    png_path = (output_dir / f"{base_name}-mobile.png").resolve()
    pdf_path = (output_dir / f"{base_name}.pdf").resolve()
    mobile_html = render_html(payload, "mobile_png")
    pdf_html = render_html(payload, "pdf")

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                mobile_page = browser.new_page(viewport={"width": 720, "height": 900}, device_scale_factor=1)
                mobile_page.set_content(mobile_html, wait_until="load")
                mobile_page.screenshot(path=str(png_path), full_page=True)
                pdf_page = browser.new_page()
                pdf_page.set_content(pdf_html, wait_until="load")
                pdf_page.pdf(path=str(pdf_path), format="Letter", print_background=True, prefer_css_page_size=True)
            finally:
                browser.close()
    except Exception as exc:
        png_path.unlink(missing_ok=True)
        pdf_path.unlink(missing_ok=True)
        raise RenderingUnavailable(
            "PNG／PDF 產出器無法啟動。請從專案根目錄執行 start_demo.cmd；"
            "若環境檢查仍失敗，請執行 .venv\\Scripts\\playwright.exe install chromium。"
            f"技術訊息：{exc}"
        ) from exc

    results = []
    for file_type, path in (("mobile_png", png_path), ("pdf", pdf_path)):
        data = path.read_bytes()
        results.append(
            {
                "file_type": file_type,
                "file_name": path.name,
                "file_path": str(path),
                "content_hash": hashlib.sha256(data).hexdigest(),
                "file_size_bytes": len(data),
            }
        )
    return results
