from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.quote import QuoteLocale


I18N_DIR = Path(__file__).resolve().parent.parent / "i18n"
SUPPORTED_LOCALES = tuple(item.value for item in QuoteLocale)


class TranslationError(RuntimeError):
    pass


@lru_cache
def get_catalog(locale: str) -> dict[str, str]:
    if locale not in SUPPORTED_LOCALES:
        raise TranslationError(f"Unsupported locale: {locale}")
    path = I18N_DIR / f"{locale}.json"
    with path.open("r", encoding="utf-8") as handle:
        catalog: dict[str, Any] = json.load(handle)
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in catalog.items()):
        raise TranslationError(f"Translation catalog must contain string values: {path.name}")
    return catalog


def translate(locale: str, key: str) -> str:
    catalog = get_catalog(locale)
    try:
        return catalog[key]
    except KeyError as exc:
        raise TranslationError(f"Missing translation key '{key}' for {locale}") from exc


def assert_catalog_completeness() -> None:
    catalogs = {locale: get_catalog(locale) for locale in SUPPORTED_LOCALES}
    reference_keys = set(catalogs[SUPPORTED_LOCALES[0]])
    for locale, catalog in catalogs.items():
        missing = reference_keys - set(catalog)
        extra = set(catalog) - reference_keys
        if missing or extra:
            raise TranslationError(
                f"Catalog {locale} differs; missing={sorted(missing)}, extra={sorted(extra)}"
            )

