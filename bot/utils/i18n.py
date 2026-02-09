"""
Internationalization helpers.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_LOCALE = "en"
LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"

_locale_cache: Dict[str, Dict[str, Any]] = {}


def _load_locale(locale: str) -> Dict[str, Any]:
    """Load locale data from JSON with a small cache."""
    if locale in _locale_cache:
        return _locale_cache[locale]

    path = LOCALES_DIR / f"{locale}.json"
    if not path.exists():
        _locale_cache[locale] = {}
        return _locale_cache[locale]

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    _locale_cache[locale] = data
    return data


def _get_nested(data: Dict[str, Any], key: str) -> Optional[str]:
    """Get a nested key using dot notation."""
    current: Any = data
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    if isinstance(current, str):
        return current
    return None


def get_user_locale(user) -> str:
    """Return the best locale for a Telegram user, defaulting to en."""
    code = getattr(user, "language_code", None) or ""
    if not code:
        return DEFAULT_LOCALE

    code = code.replace("-", "_").lower()
    if (LOCALES_DIR / f"{code}.json").exists():
        return code

    if "_" in code:
        base = code.split("_", 1)[0]
        if (LOCALES_DIR / f"{base}.json").exists():
            return base

    return DEFAULT_LOCALE


def t(key: str, locale: Optional[str] = None, **kwargs: Any) -> str:
    """Translate a key using a locale with fallback to English."""
    locale = locale or DEFAULT_LOCALE
    value = _get_nested(_load_locale(locale), key)

    if value is None and locale != DEFAULT_LOCALE:
        value = _get_nested(_load_locale(DEFAULT_LOCALE), key)

    if value is None:
        return key

    if kwargs:
        try:
            return value.format(**kwargs)
        except Exception:
            return value

    return value
