import re
from typing import Any, Dict, List, Optional

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\d{10}|\d{3}[-.\s]?\d{3}[-.\s]?\d{4})\b")
IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b")
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
DOMAIN_RE = re.compile(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b")
DATE_RE = re.compile(
    r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)
TIME_RE = re.compile(r"\b(?:\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\b", re.IGNORECASE)
TRANSACTION_ID_RE = re.compile(r"\b(?:TXN|REF|ID)[-_#]?\w{6,}\b", re.IGNORECASE)
VEHICLE_ID_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z]{1,2}\d{4}\b")
PERSON_NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")
SOCIAL_RE = re.compile(r"@[A-Za-z0-9_]{2,30}")

ENTITY_PATTERNS = [
    ("EMAIL", EMAIL_RE),
    ("PHONE", PHONE_RE),
    ("IP_ADDRESS", IPV4_RE),
    ("URL", URL_RE),
    ("DOMAIN", DOMAIN_RE),
    ("DATE", DATE_RE),
    ("TIME", TIME_RE),
    ("TRANSACTION_ID", TRANSACTION_ID_RE),
    ("VEHICLE", VEHICLE_ID_RE),
    ("SOCIAL_MEDIA_IDENTIFIER", SOCIAL_RE),
]


def _entity(value: str, entity_type: str, source_file: str, record_id: str, field: Optional[str] = None) -> Dict[str, Any]:
    return {
        "value": value.strip(),
        "type": entity_type,
        "source_file": source_file,
        "record_id": record_id,
        "field": field,
    }


def extract_entities_from_text(
    text: str,
    source_file: str,
    record_id: str,
    field: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not text or not str(text).strip():
        return []

    entities: List[Dict[str, Any]] = []
    seen = set()
    content = str(text)

    for entity_type, pattern in ENTITY_PATTERNS:
        for match in pattern.finditer(content):
            value = match.group(0).strip()
            if entity_type == "DOMAIN" and "@" in value:
                continue
            key = (entity_type, value.lower())
            if key in seen:
                continue
            seen.add(key)
            entities.append(_entity(value, entity_type, source_file, record_id, field))

    for match in PERSON_NAME_RE.finditer(content):
        value = match.group(0).strip()
        key = ("PERSON", value.lower())
        if key in seen:
            continue
        seen.add(key)
        entities.append(_entity(value, "PERSON", source_file, record_id, field))

    return entities


def extract_entities_from_record(
    record: Dict[str, Any],
    source_file: str,
    record_id: str,
) -> List[Dict[str, Any]]:
    entities: List[Dict[str, Any]] = []
    seen = set()

    for key, value in record.items():
        if value is None or value == "":
            continue
        text = str(value).strip()
        if not text:
            continue

        key_lower = str(key).lower()
        if any(token in key_lower for token in ("email", "e_mail", "mail")) and EMAIL_RE.fullmatch(text):
            item = _entity(text, "EMAIL", source_file, record_id, key)
        elif any(token in key_lower for token in ("phone", "mobile", "tel", "msisdn")) and PHONE_RE.search(text):
            item = _entity(PHONE_RE.search(text).group(0), "PHONE", source_file, record_id, key)
        elif any(token in key_lower for token in ("name", "person", "source_a", "source_b", "from", "to")):
            if re.match(r"^\d+$", text):
                item = _entity(text, "PHONE", source_file, record_id, key)
            elif "@" in text:
                item = _entity(text, "EMAIL", source_file, record_id, key)
            else:
                item = _entity(text, "PERSON", source_file, record_id, key)
        elif any(token in key_lower for token in ("org", "organization", "company")):
            item = _entity(text, "ORGANIZATION", source_file, record_id, key)
        elif any(token in key_lower for token in ("location", "address", "place")):
            item = _entity(text, "LOCATION", source_file, record_id, key)
        elif any(token in key_lower for token in ("vehicle", "vehicle_id")):
            item = _entity(text, "VEHICLE", source_file, record_id, key)
        elif any(token in key_lower for token in ("account", "iban", "wallet")):
            item = _entity(text, "ACCOUNT", source_file, record_id, key)
        elif any(token in key_lower for token in ("ip", "ip_address")):
            item = _entity(text, "IP_ADDRESS", source_file, record_id, key)
        elif any(token in key_lower for token in ("domain", "hostname")):
            item = _entity(text, "DOMAIN", source_file, record_id, key)
        elif any(token in key_lower for token in ("url", "link", "website")):
            item = _entity(text, "URL", source_file, record_id, key)
        else:
            for extracted in extract_entities_from_text(text, source_file, record_id, key):
                dedupe_key = (extracted["type"], extracted["value"].lower())
                if dedupe_key not in seen:
                    seen.add(dedupe_key)
                    entities.append(extracted)
            continue

        dedupe_key = (item["type"], item["value"].lower())
        if dedupe_key not in seen:
            seen.add(dedupe_key)
            entities.append(item)

    return entities
