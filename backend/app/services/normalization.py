import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

PHONE_RE = re.compile(r"\D")
PLATE_RE = re.compile(r"[^A-Z0-9]")
EMAIL_RE = re.compile(r"^\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\s*$")


def normalize_phone(value: str) -> str:
    digits = PHONE_RE.sub("", value or "")
    if digits.startswith("91") and len(digits) == 12:
        return digits
    if len(digits) == 10:
        return f"91{digits}"
    return digits


def normalize_plate(value: str) -> str:
    return PLATE_RE.sub("", (value or "").upper())


def normalize_email(value: str) -> str:
    match = EMAIL_RE.match(value or "")
    return match.group(1).lower() if match else (value or "").strip().lower()


def normalize_key(key: str) -> str:
    return str(key).strip().lower().replace(" ", "_")


def normalize_datetime(value: str) -> Tuple[Optional[str], str]:
    original = (value or "").strip()
    if not original:
        return None, original
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(original, fmt)
            return dt.isoformat(), original
        except ValueError:
            continue
    return None, original


def normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {"_original": dict(record)}
    for key, value in record.items():
        if value is None or (isinstance(value, float) and str(value) == "nan"):
            continue
        nk = normalize_key(key)
        text = str(value).strip()
        if not text:
            continue
        normalized[nk] = text
        if any(t in nk for t in ("phone", "caller", "receiver", "mobile", "msisdn", "source_a", "source_b")):
            if re.fullmatch(r"\+?\d{8,15}", text.replace("-", "").replace(" ", "")):
                normalized[f"normalized_{nk}"] = normalize_phone(text)
        elif any(t in nk for t in ("email", "e_mail", "mail")):
            normalized[f"normalized_{nk}"] = normalize_email(text)
        elif any(t in nk for t in ("plate", "vehicle", "registration")):
            normalized[f"normalized_{nk}"] = normalize_plate(text)
        elif any(t in nk for t in ("timestamp", "datetime", "date", "time")):
            iso, orig = normalize_datetime(text)
            normalized[f"normalized_{nk}"] = iso or orig
            normalized[f"original_{nk}"] = orig
    return normalized
