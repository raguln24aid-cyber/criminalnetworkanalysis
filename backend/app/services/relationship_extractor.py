import re
from typing import Any, Dict, List, Optional


def _relationship(
    source: str,
    relationship: str,
    target: str,
    source_file: str,
    record_id: str,
    timestamp: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "source": source,
        "relationship": relationship,
        "target": target,
        "source_file": source_file,
        "record_id": record_id,
        "timestamp": timestamp,
        "metadata": metadata or {},
        "status": "POTENTIAL LEAD",
        "note": "Investigative lead — requires independent verification. Not proof of criminal activity.",
    }


def _get_field(record: Dict[str, Any], *candidates: str) -> Optional[str]:
    normalized = {str(k).lower().replace(" ", "_"): v for k, v in record.items()}
    for candidate in candidates:
        value = normalized.get(candidate.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _is_phone(value: str) -> bool:
    return bool(re.fullmatch(r"\+?\d{8,15}", value.replace("-", "").replace(" ", "")))


def extract_relationships_from_record(
    record: Dict[str, Any],
    source_file: str,
    record_id: str,
    entities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    relationships: List[Dict[str, Any]] = []
    timestamp = _get_field(record, "timestamp", "date", "time", "datetime")
    record_type = (_get_field(record, "record_type", "type") or "").upper()

    source_a = _get_field(record, "source_a", "from", "sender", "name", "person")
    source_b = _get_field(record, "source_b", "to", "receiver", "target")
    location = _get_field(record, "location", "address", "place")
    vehicle = _get_field(record, "vehicle_id", "vehicle", "amount_or_vehicle")
    amount = _get_field(record, "amount_or_vehicle", "amount", "value")

    if record_type == "CDR" and source_a and source_b:
        rel_type = "communicates_with" if _is_phone(source_a) and _is_phone(source_b) else "associated_with"
        relationships.append(
            _relationship(source_a, rel_type, source_b, source_file, record_id, timestamp)
        )
        if location:
            relationships.append(
                _relationship(source_a, "located_at", location, source_file, record_id, timestamp)
            )

    elif record_type == "TRANSACTION" and source_a and source_b:
        relationships.append(
            _relationship(source_a, "transferred_to", source_b, source_file, record_id, timestamp, {"amount": amount})
        )

    elif record_type == "VEHICLE" and source_a:
        if vehicle:
            relationships.append(
                _relationship(source_a, "uses", vehicle, source_file, record_id, timestamp)
            )
        if location:
            relationships.append(
                _relationship(source_a, "located_at", location, source_file, record_id, timestamp)
            )

    elif record_type == "LOCATION" and source_a and location:
        relationships.append(
            _relationship(source_a, "located_at", location, source_file, record_id, timestamp)
        )

    else:
        if source_a and source_b:
            rel_type = "communicates_with" if _is_phone(source_a) and _is_phone(source_b) else "associated_with"
            relationships.append(
                _relationship(source_a, rel_type, source_b, source_file, record_id, timestamp)
            )
        if source_a and location:
            relationships.append(
                _relationship(source_a, "located_at", location, source_file, record_id, timestamp)
            )
        if source_a and vehicle:
            relationships.append(
                _relationship(source_a, "uses", vehicle, source_file, record_id, timestamp)
            )

    entity_map = {(e["type"], e["value"].lower()): e for e in entities}
    for entity in entities:
        if entity["type"] == "EMAIL":
            person_candidates = [
                e for e in entities
                if e["type"] == "PERSON" and e["record_id"] == record_id
            ]
            for person in person_candidates:
                relationships.append(
                    _relationship(
                        person["value"],
                        "uses",
                        entity["value"],
                        source_file,
                        record_id,
                        timestamp,
                    )
                )
        if entity["type"] == "PHONE":
            person_candidates = [
                e for e in entities
                if e["type"] == "PERSON" and e["record_id"] == record_id
            ]
            for person in person_candidates:
                if person["value"].lower() != entity["value"].lower():
                    relationships.append(
                        _relationship(
                            person["value"],
                            "owns",
                            entity["value"],
                            source_file,
                            record_id,
                            timestamp,
                        )
                    )

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for rel in relationships:
        key = (rel["source"].lower(), rel["relationship"], rel["target"].lower(), rel["record_id"])
        if key not in seen:
            seen.add(key)
            deduped.append(rel)
    return deduped
