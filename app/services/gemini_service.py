from __future__ import annotations

import base64
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import json
import re
from typing import Any

import httpx

from app.config import get_settings
from app.schemas.quote import CoverageItem, Customer, PlanItem, Policy, QuoteDraft, QuoteLocale
from app.services.preset_service import get_coverage_presets


class GeminiExtractionError(Exception):
    """Raised when Gemini PDF extraction fails with a user-friendly message."""
    pass


EXTRACTION_PROMPT = """You are an expert insurance document parser.
Analyze this insurance quote / declaration (Dec) page PDF document and extract all available information into a structured JSON object.

Extraction Guidelines:
1. Customer Name: Full name of the insured / applicant.
2. Carrier Name: Insurance company name (e.g. Progressive, Mercury, Geico, State Farm, Travelers, Allstate, etc.).
3. Policy Term: Duration in months (usually 6 or 12).
4. Quote / Effective Date: Date of quote or effective date (YYYY-MM-DD). If unclear, use today's date.
5. Expiration Date: Expiration / valid-until date (YYYY-MM-DD). If not specified, leave as null.
6. Vehicle & Drivers:
   - vehicle_summary: Concise text of vehicles (e.g. "2023 Toyota RAV4" or "2020 Honda Civic / 2022 Ford F-150").
   - vehicle_count: Integer number of vehicles (default 1).
   - driver_count: Integer number of drivers (default 1).
   - garaging_zip: Garaging postal code (5 digits).
7. Coverages: List each coverage found with:
   - standard_code: Match to one of:
     ["bodily_injury", "property_damage", "uninsured_motorist", "collision_deductible", "comprehensive_deductible", "medical_payments", "rental_reimbursement", "roadside_assistance", "glass_coverage", "gap_coverage"]
     If it does not match any of these standard codes, set standard_code to "custom".
   - name_in_pdf: The exact or descriptive name shown in the document.
   - value: The limit or deductible value (e.g. "$50,000 / $100,000", "$1,000", "$500", "Included", "Not included", "$30/day, max 30 days", etc.).
   - custom_label: If standard_code is "custom", provide a concise label.
   - custom_description: Optional brief description if custom.
8. Plans & Premiums:
   - List the auto insurance plan and any bundle / alternative plans mentioned.
   - Extract premium_total as a numeric string (e.g. "1135.69" or "850.00"). Do not include currency symbols.
   - premium_period: "6_month_policy" or "annual_policy".
   - plan_code: "auto_only", "auto_renters", or "alternative".
   - recommended: Boolean (true if this is the recommended or primary package).
   - short_note: Any brief note or summary about the plan.

Return ONLY a valid JSON object matching this structure:
{
  "customer_name": "string",
  "carrier_name": "string",
  "term_months": 6,
  "quote_date": "YYYY-MM-DD",
  "expiration_date": "YYYY-MM-DD or null",
  "vehicle_summary": "string",
  "vehicle_count": 1,
  "driver_count": 1,
  "garaging_zip": "string",
  "coverages": [
    {
      "standard_code": "bodily_injury",
      "name_in_pdf": "Bodily Injury Liability",
      "value": "$50,000 / $100,000",
      "custom_label": null,
      "custom_description": null
    }
  ],
  "plans": [
    {
      "plan_code": "auto_only",
      "display_name": "Auto Only",
      "premium_total": "1135.69",
      "premium_period": "6_month_policy",
      "recommended": false,
      "short_note": ""
    }
  ],
  "notes": "string"
}
"""


def clean_json_text(text: str) -> str:
    """Strip markdown code fence if present."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def parse_date_safe(val: Any, default: date) -> date:
    if not val or not isinstance(val, str):
        return default
    try:
        # Match YYYY-MM-DD
        match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", val.strip())
        if match:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        # Match MM/DD/YYYY
        match_slash = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", val.strip())
        if match_slash:
            return date(int(match_slash.group(3)), int(match_slash.group(1)), int(match_slash.group(2)))
    except Exception:
        pass
    return default


def parse_decimal_safe(val: Any) -> Decimal | None:
    if val is None:
        return None
    if isinstance(val, (int, float, Decimal)):
        try:
            return Decimal(str(val)).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError):
            return None
    if isinstance(val, str):
        cleaned = re.sub(r"[^\d.]", "", val.strip())
        if cleaned:
            try:
                return Decimal(cleaned).quantize(Decimal("0.01"))
            except (InvalidOperation, TypeError):
                return None
    return None


def extract_raw_json_from_gemini(pdf_bytes: bytes, api_key: str | None = None, model: str | None = None) -> dict[str, Any]:
    """Send PDF bytes to Gemini API and parse structured JSON response."""
    settings = get_settings()
    key = (api_key or settings.gemini_api_key or "").strip().strip("'\"").strip()
    if not key or key == "your-gemini-api-key-here" or "replace-me" in key or key.startswith("your-"):
        raise GeminiExtractionError(
            "系統尚未設定有效的 GEMINI_API_KEY（目前 .env 中的值仍為預設範例文字 'your-gemini-api-key-here'）。"
            "請打開專案根目錄的 .env 檔案，將 GEMINI_API_KEY 改為您在 Google AI Studio 取得的真實金鑰 (AIzaSy... 開頭)。"
        )


    raw_model = (model or settings.gemini_model or "gemini-3.7-flash").strip().strip("'\"").strip()
    primary_model = raw_model.replace("models/", "")
    
    # 2026 GA candidate models (gemini-3.7-flash, gemini-3.6-flash, gemini-flash alias)
    fallback_candidates = [primary_model, "gemini-3.7-flash", "gemini-3.6-flash", "gemini-flash"]
    models_to_try = []
    for m in fallback_candidates:
        if m and m not in models_to_try:
            models_to_try.append(m)

    b64_data = base64.b64encode(pdf_bytes).decode("utf-8")

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "application/pdf",
                            "data": b64_data,
                        }
                    },
                    {
                        "text": EXTRACTION_PROMPT,
                    },
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    }

    headers = {
        "x-goog-api-key": key,
        "Content-Type": "application/json",
    }

    import time
    last_error_message = ""

    with httpx.Client(timeout=60.0) as client:
        for current_model in models_to_try:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent"
            # Try up to 2 times for current model if transient error occurs
            for attempt in range(2):
                try:
                    response = client.post(api_url, json=payload, headers=headers)
                except httpx.TimeoutException:
                    last_error_message = f"Gemini API ({current_model}) 連線逾時（超過 60 秒）"
                    continue
                except Exception as exc:
                    last_error_message = f"無法連線至 Gemini API 服務 ({current_model})：{exc}"
                    continue

                if response.status_code == 200:
                    try:
                        res_data = response.json()
                        candidates = res_data.get("candidates", [])
                        if not candidates:
                            raise GeminiExtractionError("Gemini 未能產生有效回應，請確認 PDF 內容是否清晰可讀。")

                        first_part = candidates[0].get("content", {}).get("parts", [{}])[0]
                        raw_text = first_part.get("text", "")
                        if not raw_text:
                            raise GeminiExtractionError("Gemini 回傳了空白內容。")

                        cleaned = clean_json_text(raw_text)
                        extracted = json.loads(cleaned)
                        if not isinstance(extracted, dict):
                            raise GeminiExtractionError("Gemini 回傳格式不符合預期的 JSON 物件。")
                        return extracted
                    except json.JSONDecodeError as exc:
                        raise GeminiExtractionError(f"解析 Gemini 回傳的 JSON 失敗：{exc}")

                # Error extraction
                err_detail = ""
                try:
                    err_json = response.json()
                    err_detail = err_json.get("error", {}).get("message", response.text)
                except Exception:
                    err_detail = response.text

                last_error_message = f"Gemini API ({current_model}) 回應 {response.status_code}：{err_detail}"

                # 503 / 429: Rate limit or high demand -> retry or switch model
                if response.status_code in (503, 429):
                    time.sleep(1.5)
                    continue
                # 404: Model not found or retired -> switch to next fallback model immediately
                elif response.status_code == 404:
                    break
                # 400 / 401 / 403: Fatal configuration / authentication error
                else:
                    raise GeminiExtractionError(last_error_message)

    raise GeminiExtractionError(f"Gemini API 暫時無法處理請求（已嘗試所有 2026 現役備援模型）：{last_error_message}")



def map_extraction_to_draft(

    extracted: dict[str, Any],
    user_id: int,
    quote_number: str,
    locale: QuoteLocale = QuoteLocale.ZH_TW,
) -> QuoteDraft:
    """Map raw extracted JSON from Gemini into a validated QuoteDraft object."""
    today = date.today()
    q_date = parse_date_safe(extracted.get("quote_date"), today)
    exp_default = q_date + timedelta(days=10)
    exp_date = parse_date_safe(extracted.get("expiration_date"), exp_default)
    if exp_date <= q_date:
        exp_date = q_date + timedelta(days=10)

    # Customer
    customer_name = str(extracted.get("customer_name") or "").strip()
    customer = Customer(name=customer_name)

    # Policy
    carrier = str(extracted.get("carrier_name") or "").strip()
    term_months = int(extracted.get("term_months") or 6)
    if term_months not in (6, 12):
        term_months = 6 if term_months < 9 else 12

    vehicle_count = int(extracted.get("vehicle_count") or 1)
    driver_count = int(extracted.get("driver_count") or 1)
    vehicle_summary = str(extracted.get("vehicle_summary") or "").strip()
    garaging_zip = str(extracted.get("garaging_zip") or "").strip()

    policy = Policy(
        carrier=carrier,
        term_months=term_months,
        quote_date=q_date,
        expiration_date=exp_date,
        vehicle_summary=vehicle_summary,
        vehicle_count=max(0, min(20, vehicle_count)),
        driver_count=max(0, min(20, driver_count)),
        garaging_zip=garaging_zip[:10],
    )

    # Coverages
    presets = get_coverage_presets()
    preset_codes = {item["code"]: item for item in presets}
    known_order = {item["code"]: item.get("sort_order", idx * 10 + 10) for idx, item in enumerate(presets)}

    coverages: list[CoverageItem] = []
    raw_coverages = extracted.get("coverages") or []

    for idx, raw in enumerate(raw_coverages):
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("standard_code") or "").strip()
        name_in_pdf = str(raw.get("name_in_pdf") or "").strip()
        val = str(raw.get("value") or "").strip()
        custom_label = raw.get("custom_label")
        custom_desc = raw.get("custom_description")

        # If standard code matched
        if code in preset_codes:
            sort_order = known_order.get(code, (idx + 1) * 10)
            coverages.append(
                CoverageItem(
                    code=code,
                    value=val or "$50,000 / $100,000",
                    sort_order=sort_order,
                    custom_label=None,
                    custom_description=None,
                )
            )
        else:
            # Custom coverage
            custom_code = f"custom_{idx + 1}"
            label = custom_label or name_in_pdf or f"保障項目 {idx + 1}"
            coverages.append(
                CoverageItem(
                    code=custom_code,
                    value=val or "Included",
                    sort_order=(idx + 1) * 10 + 100,
                    custom_label=label,
                    custom_description=custom_desc or "",
                )
            )

    # If no coverages were extracted, seed default 4 basics
    if not coverages:
        coverages = [
            CoverageItem(code="bodily_injury", value="$50,000 / $100,000", sort_order=10),
            CoverageItem(code="property_damage", value="$100,000", sort_order=20),
            CoverageItem(code="collision_deductible", value="$1,000", sort_order=30),
            CoverageItem(code="comprehensive_deductible", value="$500", sort_order=40),
        ]

    # Sort coverages by sort_order
    coverages.sort(key=lambda c: c.sort_order)

    # Plans
    plans: list[PlanItem] = []
    raw_plans = extracted.get("plans") or []
    has_auto_renters = False

    for idx, raw_plan in enumerate(raw_plans):
        if not isinstance(raw_plan, dict):
            continue
        p_code = str(raw_plan.get("plan_code") or f"plan_{idx+1}").strip()
        if p_code not in ("auto_only", "auto_renters", "alternative"):
            p_code = "auto_only" if idx == 0 else ("auto_renters" if idx == 1 else "alternative")
        
        if p_code == "auto_renters":
            has_auto_renters = True

        prem = parse_decimal_safe(raw_plan.get("premium_total"))
        period = str(raw_plan.get("premium_period") or "6_month_policy").strip()
        if period not in ("6_month_policy", "annual_policy"):
            period = "6_month_policy"

        rec = bool(raw_plan.get("recommended", False))
        note = str(raw_plan.get("short_note") or "").strip()
        disp_name = raw_plan.get("display_name")

        plans.append(
            PlanItem(
                plan_code=p_code,
                premium_total=prem,
                premium_period=period,
                recommended=rec,
                short_note=note,
                sort_order=(idx + 1) * 10,
                display_name=disp_name,
            )
        )

    # Ensure we have at least auto_only and auto_renters
    if not plans:
        plans = [
            PlanItem(plan_code="auto_only", premium_total=None, sort_order=10),
            PlanItem(plan_code="auto_renters", premium_total=None, recommended=True, sort_order=20),
        ]
    elif not has_auto_renters and len(plans) == 1:
        plans.append(
            PlanItem(plan_code="auto_renters", premium_total=None, recommended=True, sort_order=20)
        )

    # Notes
    raw_notes = str(extracted.get("notes") or "").strip()
    customer_facing_note = ""
    internal_note = f"由 PDF 智慧辨識匯入 ({carrier or 'Carrier Unknown'})"
    if raw_notes:
        internal_note += f" - {raw_notes}"

    return QuoteDraft(
        quote_number=quote_number,
        locale=locale,
        currency="USD",
        customer=customer,
        policy=policy,
        coverages=coverages,
        plans=plans,
        agent_id=user_id,
        customer_facing_note=customer_facing_note,
        internal_note=internal_note,
    )


def extract_quote_from_pdf(
    pdf_bytes: bytes,
    user_id: int,
    quote_number: str,
    locale: QuoteLocale = QuoteLocale.ZH_TW,
    api_key: str | None = None,
    model: str | None = None,
) -> QuoteDraft:
    """End-to-end extraction from PDF bytes into a QuoteDraft instance."""
    raw_json = extract_raw_json_from_gemini(pdf_bytes, api_key=api_key, model=model)
    return map_extraction_to_draft(raw_json, user_id=user_id, quote_number=quote_number, locale=locale)
