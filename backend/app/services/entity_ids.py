import hashlib
import re
from typing import Optional

from app.services.normalization import normalize_email, normalize_phone, normalize_plate


def _hash_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def normalize_entity_value(entity_type: str, value: str) -> str:
    et = entity_type.upper()
    if et in ("PHONE",):
        return normalize_phone(value)
    if et in ("EMAIL",):
        return normalize_email(value)
    if et in ("VEHICLE", "NUMBER_PLATE"):
        return normalize_plate(value)
    if et in ("PERSON", "ORGANIZATION", "LOCATION", "EVENT"):
        return re.sub(r"\s+", " ", value.strip()).lower()
    return value.strip().lower()


def entity_id(entity_type: str, value: str) -> str:
    prefix_map = {
        "PERSON": "PER",
        "PHONE": "PHN",
        "EMAIL": "EML",
        "VEHICLE": "VEH",
        "NUMBER_PLATE": "PLT",
        "LOCATION": "LOC",
        "ORGANIZATION": "ORG",
        "EVENT": "EVT",
        "ACCOUNT": "ACC",
        "DEVICE": "DEV",
        "TRANSACTION": "TXN",
        "IP_ADDRESS": "IP",
        "DOMAIN": "DOM",
        "URL": "URL",
        "DATE": "DAT",
        "TIME": "TIM",
        "DATETIME": "DTM",
    }
    prefix = prefix_map.get(entity_type.upper(), "ENT")
    normalized = normalize_entity_value(entity_type, value)
    return _hash_id(prefix, f"{entity_type.upper()}:{normalized}")
