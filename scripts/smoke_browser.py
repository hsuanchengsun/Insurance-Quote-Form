from __future__ import annotations

import sys
import os
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8030").rstrip("/")
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "generated"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    page_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        health_response = page.request.get(f"{BASE_URL}/health")
        assert health_response.ok
        health = health_response.json()
        assert health["status"] == "ok" and health["renderer"]["ready"] is True

        page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        assert page.get_by_role("heading", name="專員登入").is_visible()
        page.get_by_label("帳號").fill("agent")
        page.get_by_label("密碼").fill("demo1234")
        page.get_by_role("button", name="登入工作區").click()
        page.wait_for_url(f"{BASE_URL}/")
        assert page.get_by_role("heading", name="報價管理").is_visible()
        page.screenshot(path=str(OUTPUT_DIR / "ui-quote-list.png"), full_page=True)

        first_edit = page.get_by_role("link", name="編輯").first
        first_edit.click()
        page.wait_for_url(lambda url: "/quotes/" in url and url.endswith("/edit"))
        assert page.get_by_role("heading", name="基本資料").is_visible()
        page.locator("#preview-frame").wait_for(state="visible")
        page.wait_for_timeout(1000)
        preview_srcdoc = page.locator("#preview-frame").get_attribute("srcdoc")
        if not preview_srcdoc:
            page.screenshot(path=str(OUTPUT_DIR / "ui-preview-debug.png"), full_page=False)
            raise AssertionError(
                "Preview iframe did not receive srcdoc; loading="
                + str(page.locator("#preview-empty").text_content())
                + "; console=" + " | ".join(console_errors)
                + "; page-errors=" + " | ".join(page_errors)
            )
        assert page.locator("#preview-empty").is_hidden(), (
            "Preview loading overlay remained visible; console errors=" + " | ".join(console_errors)
        )
        assert page.locator(".visible-mobile, .visible-pdf").count() == 0
        preview_metrics = page.evaluate(
            """() => {
              const wrapper = document.querySelector('#preview-frame-wrap');
              const frame = document.querySelector('#preview-frame');
              const doc = frame.contentDocument;
              return {
                wrapperClientWidth: wrapper.clientWidth,
                wrapperScrollWidth: wrapper.scrollWidth,
                frameClientHeight: frame.clientHeight,
                documentScrollHeight: doc.documentElement.scrollHeight,
                brandVisible: doc.querySelector('.brand')?.textContent.includes('Quote Builder'),
                qrAbsent: doc.querySelector('.qr-image') === null
              };
            }"""
        )
        assert preview_metrics["wrapperScrollWidth"] <= preview_metrics["wrapperClientWidth"] + 1
        assert preview_metrics["documentScrollHeight"] <= preview_metrics["frameClientHeight"] + 1
        assert preview_metrics["brandVisible"] and preview_metrics["qrAbsent"]
        assert page.locator("[data-preview]").count() == 0

        page.locator("#locale").select_option("zh-CN")
        page.wait_for_function(
            "document.querySelector('#preview-frame')?.contentDocument?.body?.innerText.includes('汽车保险报价') === true"
        )
        page.locator("#locale").select_option("en-US")
        page.wait_for_function(
            "document.querySelector('#preview-frame')?.contentDocument?.body?.innerText.includes('Auto Insurance Quote') === true"
        )
        page.locator("#locale").select_option("zh-TW")
        page.wait_for_function(
            "document.querySelector('#preview-frame')?.contentDocument?.body?.innerText.includes('汽車保險報價') === true"
        )
        page.screenshot(path=str(OUTPUT_DIR / "ui-quote-editor.png"), full_page=False)

        browser.close()

    if console_errors:
        raise SystemExit("Browser console errors: " + " | ".join(console_errors))
    print("Browser smoke test passed: login, quote list, editor, language switching, unified preview")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Browser smoke test failed: {exc!r}")
        traceback.print_exc()
        sys.exit(1)
