from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class QuoteLocale(str, Enum):
    ZH_TW = "zh-TW"
    ZH_CN = "zh-CN"
    EN_US = "en-US"


class Customer(BaseModel):
    name: str = ""


class Policy(BaseModel):
    carrier: str = ""
    term_months: int = Field(default=6, ge=1, le=24)
    quote_date: date
    expiration_date: date
    vehicle_summary: str = ""
    vehicle_count: int = Field(default=1, ge=0, le=20)
    driver_count: int = Field(default=1, ge=0, le=20)
    garaging_zip: str = ""


class CoverageItem(BaseModel):
    code: str
    value: str = ""
    sort_order: int = 10
    custom_label: str | None = None
    custom_description: str | None = None


class PlanItem(BaseModel):
    plan_code: str
    premium_total: Decimal | None = None
    premium_period: str = "6_month_policy"
    recommended: bool = False
    short_note: str = ""
    sort_order: int = 10
    display_name: str | None = None


class QuoteDraft(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    quote_number: str = ""
    locale: QuoteLocale = QuoteLocale.ZH_TW
    currency: str = "USD"
    customer: Customer
    policy: Policy
    coverages: list[CoverageItem] = Field(default_factory=list)
    plans: list[PlanItem] = Field(default_factory=list)
    agent_id: int
    customer_facing_note: str = ""
    internal_note: str = ""


class GenerationRequest(BaseModel):
    draft: QuoteDraft
    acknowledge_warnings: bool = False
    change_note: str = ""
