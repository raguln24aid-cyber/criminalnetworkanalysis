import os
import re
import json
import logging
from collections import defaultdict
from typing import TypedDict, Any, List, Optional
from langgraph.graph import StateGraph, START, END
from app.neo4j_db import neo4j_service
from app.config import get_settings
from sqlalchemy.orm import Session
from app.models.domain import IngestedDocument
from app.database import SessionLocal
import pandas as pd
from uuid import uuid4

# Import PHASE 1 services
from app.services.llm_entity_extractor import extract_entities_llm_record, batch_extract_entities_llm
from app.services.entity_resolution import entity_resolver, resolve_entity, ResolvedEntity
from app.services.entity_ids import normalize_entity_value
from app.services.common_json_normalizer import (
    normalize_entity_data,
    normalize_relationship_data,
    validate_entity,
    batch_normalize_entities,
    batch_normalize_relationships
)

settings = get_settings()
logger = logging.getLogger(__name__)

class InvestigationState(TypedDict, total=False):
    document_id: str
    source_file: str
    uploaded_by: str
    source_type: str
    raw_content: Any
    cleaned_content: Any
    structured_records: list
    entities: list
    relationships: list
    events: list
    evidence: list
    graph_nodes: list
    graph_edges: list
    processing_status: str
    processing_progress: int
    errors: list

def update_document_progress(document_id: str, stage: str, progress: int, status: str = "processing", **kwargs):
    db = SessionLocal()
    try:
        doc = db.query(IngestedDocument).filter(IngestedDocument.id == document_id).first()
        if doc:
            doc.stage = stage
            doc.progress = progress
            doc.status = status
            for k, v in kwargs.items():
                setattr(doc, k, v)
            db.commit()
    finally:
        db.close()


def create_evidence_record(document_id: str, source_file: str, source_type: str,
                            records_count: int, entities_count: int, relationships_count: int) -> Optional[str]:
    """
    Creates a tamper-evident ledger record (Evidence.hash) for a fully
    processed document and links it back onto IngestedDocument.evidence_id -
    the field existed in the schema already but nothing ever populated it,
    which is why Evidence Explorer's "Verify Integrity" always reported
    TAMPER DETECTED (no Evidence row ever existed to compare against).
    """
    from datetime import datetime, timezone
    from app.models.domain import Evidence
    from app.evidence.ledger import ledger

    db = SessionLocal()
    try:
        evidence_id = f"EV_{uuid4().hex[:10].upper()}"
        timestamp = datetime.now(timezone.utc).isoformat()
        source = source_file
        confidence = 1.0
        content = json.dumps({
            "document_id": document_id,
            "source_file": source_file,
            "source_type": source_type,
            "records_processed": records_count,
            "entities_found": entities_count,
            "relationships_found": relationships_count,
        }, sort_keys=True)

        # Chain this record to whichever evidence record was created most
        # recently, so tampering with (or deleting/reordering) any earlier
        # record breaks the hash of everything after it - not just that one
        # record in isolation. Hash exactly the fields verify_integrity()
        # will later recompute from the stored row (id, source, timestamp,
        # confidence, content) - they must match field-for-field or every
        # fresh record would fail its own first verification.
        previous_hash = ledger.get_latest_hash(db)
        evidence_hash = ledger.create_evidence_hash({
            "id": evidence_id,
            "source": source,
            "timestamp": timestamp,
            "confidence": confidence,
            "content": content,
        }, previous_hash)

        db.add(Evidence(
            id=evidence_id,
            hash=evidence_hash,
            previous_hash=previous_hash,
            timestamp=timestamp,
            source=source,
            confidence=confidence,
            processing_version=settings.VERSION,
            content=content,
        ))

        doc = db.query(IngestedDocument).filter(IngestedDocument.id == document_id).first()
        if doc:
            doc.evidence_id = evidence_id
        db.commit()
        return evidence_id
    except Exception as e:
        logger.error(f"[EVIDENCE] Failed to create evidence record for {document_id}: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def fail_document(state: "InvestigationState", message: str, progress: int) -> "InvestigationState":
    """
    Mark a document as failed both in the in-memory workflow state and in the
    database, so the frontend can stop polling and show a real error instead
    of hanging at whatever the last successful progress checkpoint was.
    """
    logger.error(f"[WORKFLOW] Document {state.get('document_id')} failed: {message}")
    state["processing_status"] = "failed"
    state["errors"] = state.get("errors", []) + [message]
    update_document_progress(
        state["document_id"], "Failed", progress, status="failed", error_message=message
    )
    _audit_processing_event(state, "PROCESSING_FAILED", "FAILURE", {"error": message})
    return state


def _audit_processing_event(state: "InvestigationState", action: str, result: str, details: Optional[dict] = None):
    """Background-task processing has no HTTP request/current_user to hang an
    audit entry off of, so the acting username is threaded through the
    workflow state from the /data/upload call instead (see endpoints.py)."""
    from app.services.audit_service import log_action

    db = SessionLocal()
    try:
        log_action(
            db,
            state.get("uploaded_by") or "unknown",
            action,
            "document",
            state.get("document_id"),
            result=result,
            details=details,
        )
    finally:
        db.close()

def document_router(state: InvestigationState) -> InvestigationState:
    update_document_progress(state["document_id"], "Detecting document", 10)
    source_file = state["source_file"]
    ext = os.path.splitext(source_file)[1].lower()
    
    if ext == ".csv":
        state["source_type"] = "csv"
    elif ext == ".json":
        state["source_type"] = "json"
    elif ext == ".txt":
        state["source_type"] = "txt"
    elif ext == ".pdf":
        state["source_type"] = "pdf"
    else:
        state["source_type"] = "unknown"
        state["errors"] = state.get("errors", []) + ["Unsupported file type"]
    
    return state

def route_preprocessor(state: InvestigationState) -> str:
    source_type = state.get("source_type", "unknown")
    if source_type == "csv":
        return "csv_preprocessor"
    elif source_type == "json":
        return "json_preprocessor"
    elif source_type == "txt":
        return "txt_preprocessor"
    elif source_type == "pdf":
        return "pdf_preprocessor"
    return END

def csv_preprocessor(state: InvestigationState) -> InvestigationState:
    update_document_progress(state["document_id"], "Extracting content", 20)
    source_file = state["source_file"]
    file_path = os.path.join(settings.UPLOAD_DIR, source_file)
    try:
        df = pd.read_csv(file_path)
        # Normalize column names
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        df = df.dropna(how='all')
        records = df.to_dict(orient="records")
        state["structured_records"] = records
        update_document_progress(state["document_id"], "Extracting content", 30, records_processed=len(records))
    except Exception as e:
        fail_document(state, f"CSV error: {str(e)}", 20)
    return state

def json_preprocessor(state: InvestigationState) -> InvestigationState:
    update_document_progress(state["document_id"], "Extracting content", 20)
    source_file = state["source_file"]
    file_path = os.path.join(settings.UPLOAD_DIR, source_file)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            state["structured_records"] = [data]
        elif isinstance(data, list):
            state["structured_records"] = data
        update_document_progress(state["document_id"], "Extracting content", 30, records_processed=len(state["structured_records"]))
    except Exception as e:
        fail_document(state, f"JSON error: {str(e)}", 20)
    return state

def txt_preprocessor(state: InvestigationState) -> InvestigationState:
    update_document_progress(state["document_id"], "Extracting content", 20)
    source_file = state["source_file"]
    file_path = os.path.join(settings.UPLOAD_DIR, source_file)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        state["raw_content"] = content
        # Basic chunking by lines for MVP
        chunks = [line.strip() for line in content.split('\n') if line.strip()]
        state["structured_records"] = [{"text": chunk, "line": i} for i, chunk in enumerate(chunks)]
        update_document_progress(state["document_id"], "Extracting content", 30, records_processed=len(chunks))
    except Exception as e:
        fail_document(state, f"TXT error: {str(e)}", 20)
    return state

def pdf_preprocessor(state: InvestigationState) -> InvestigationState:
    update_document_progress(state["document_id"], "Extracting content", 20)
    source_file = state["source_file"]
    file_path = os.path.join(settings.UPLOAD_DIR, source_file)
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                pages.append({"text": text.strip(), "page": i + 1})
        state["structured_records"] = pages
        update_document_progress(state["document_id"], "Extracting content", 30, records_processed=len(pages))
    except Exception as e:
        fail_document(state, f"PDF error: {str(e)}", 20)
    return state

def normalization_agent(state: InvestigationState) -> InvestigationState:
    if state.get("processing_status") == "failed":
        return state
    update_document_progress(state["document_id"], "Normalizing", 40)
    # MVP Normalization: clean up strings in structured records
    records = state.get("structured_records", [])
    normalized_records = []
    for r in records:
        nr = {}
        for k, v in r.items():
            if isinstance(v, str):
                nr[k] = v.strip()
                if "plate" in k or "vehicle" in k:
                    nr[f"normalized_{k}"] = v.strip().replace(" ", "").upper()
                elif "phone" in k or "caller" in k or "receiver" in k:
                    nr[f"normalized_{k}"] = v.strip().replace("-", "").replace(" ", "")
            else:
                nr[k] = v
        normalized_records.append(nr)
    state["structured_records"] = normalized_records
    return state

def entity_extraction_agent(state: InvestigationState) -> InvestigationState:
    """
    PHASE 1: LLM-based entity extraction with deterministic fallback.
    
    Uses LLM entity extractor first, falls back to deterministic extraction.
    Preserves all existing functionality while adding LLM capabilities.
    """
    if state.get("processing_status") == "failed":
        return state
    update_document_progress(state["document_id"], "Extracting entities", 50)
    
    records = state.get("structured_records", [])
    entities = []
    
    # PHASE 1: Try LLM extraction first
    llm_used = False
    try:
        source_type = state.get("source_type", "unknown")
        document_id = state.get("document_id", "unknown")
        source_file = state.get("source_file", "unknown")
        
        # Use LLM extractor for structured records
        if records:
            raw_entities = batch_extract_entities_llm(
                records, source_file, document_id, source_type
            )
            entities = raw_entities
            llm_used = True
            logger.info(f"[PHASE1] LLM extracted {len(entities)} entities from {len(records)} records")
        
    except Exception as e:
        logger.warning(f"[PHASE1] LLM entity extraction failed, falling back to deterministic: {e}")
        llm_used = False
    
    # Fallback to deterministic extraction if LLM failed or wasn't used
    if not llm_used or not entities:
        logger.info("[PHASE1] Using deterministic entity extraction")
        entities = []
        
        # Deterministic MVP mapping (preserved from original)
        for i, r in enumerate(records):
            evidence_ref = {"document_id": state["document_id"], "file": state["source_file"], "row": i}
            
            # Look for PERSON
            for p_key in ["person", "person_name", "name", "customer_name", "caller_name", "subscriber", "owner"]:
                if p_key in r and pd.notna(r[p_key]):
                    val = str(r[p_key]).strip()
                    if val:
                        entities.append({"type": "PERSON", "value": val, "normalized_value": val.lower(), "evidence": evidence_ref})
            
            # Look for PHONE
            for ph_key in ["phone", "caller", "receiver", "calling_number", "receiving_number", "contact"]:
                if ph_key in r and pd.notna(r[ph_key]):
                    val = str(r[ph_key]).strip()
                    if val:
                        entities.append({"type": "PHONE", "value": val, "normalized_value": r.get(f"normalized_{ph_key}", val), "evidence": evidence_ref})
                        
            # Look for VEHICLE
            for v_key in ["vehicle_no", "vehicle_number", "registration", "registration_number", "plate"]:
                if v_key in r and pd.notna(r[v_key]):
                    val = str(r[v_key]).strip()
                    if val:
                        entities.append({"type": "VEHICLE", "value": val, "normalized_value": r.get(f"normalized_{v_key}", val), "evidence": evidence_ref})
                        
            # Look for ORGANIZATION
            for o_key in ["organization", "company", "org"]:
                if o_key in r and pd.notna(r[o_key]):
                    val = str(r[o_key]).strip()
                    if val:
                        entities.append({"type": "ORGANIZATION", "value": val, "normalized_value": val.lower(), "evidence": evidence_ref})
                        
            # Look for LOCATION
            for l_key in ["location", "address", "city", "tower"]:
                if l_key in r and pd.notna(r[l_key]):
                    val = str(r[l_key]).strip()
                    if val:
                        entities.append({"type": "LOCATION", "value": val, "normalized_value": val.lower(), "evidence": evidence_ref})
    
    # PHASE 1: Add extraction method tracking
    for entity in entities:
        if "extraction_method" not in entity:
            entity["extraction_method"] = "deterministic" if not llm_used else "llm"
        if "document_id" not in entity:
            entity["document_id"] = state["document_id"]
        if "source_file" not in entity:
            entity["source_file"] = state["source_file"]
        if "source_type" not in entity:
            entity["source_type"] = state.get("source_type", "unknown")
    
    state["entities"] = entities
    update_document_progress(state["document_id"], "Extracting entities", 60, entities_found=len(entities))
    return state


def entity_resolution_agent(state: InvestigationState) -> InvestigationState:
    """
    PHASE 1: Entity resolution for cross-document deduplication.
    
    Resolves entities to consistent IDs and tracks provenance across documents.
    """
    if state.get("processing_status") == "failed":
        return state
    update_document_progress(state["document_id"], "Resolving entities", 65)
    
    raw_entities = state.get("entities", [])
    resolved_entities = []
    
    try:
        # Clear resolver for this document to avoid cross-document pollution
        # In production, you might want a persistent resolver
        entity_resolver.clear()
        
        for entity in raw_entities:
            entity_type = entity.get("type", entity.get("entity_type", "UNKNOWN"))
            value = entity.get("value", entity.get("original_value", ""))
            
            # Extract provenance from entity or state
            provenance = {
                "document_id": entity.get("document_id", state.get("document_id", "unknown")),
                "source_file": entity.get("source_file", state.get("source_file", "unknown")),
                "source_type": entity.get("source_type", state.get("source_type", "unknown")),
                "row": entity.get("row", entity.get("evidence", {}).get("row")),
                "extraction_method": entity.get("extraction_method", "unknown"),
                "confidence": entity.get("confidence", 1.0)
            }
            
            # Resolve entity to consistent ID
            resolved_entity = entity_resolver.resolve(
                entity_type, 
                str(value), 
                provenance
            )
            
            # Convert to dict format expected by downstream agents
            resolved_entities.append({
                "type": resolved_entity.entity_type,
                "value": resolved_entity.original_value,
                "normalized_value": resolved_entity.normalized_value,
                "id": resolved_entity.resolved_id,  # Add resolved ID
                "resolved_id": resolved_entity.resolved_id,
                "confidence": resolved_entity.confidence,
                "provenance": provenance,
                "extraction_method": entity.get("extraction_method", "deterministic"),
                "document_id": state.get("document_id"),
                "source_file": state.get("source_file"),
                "source_type": state.get("source_type")
            })
        
        logger.info(f"[PHASE1] Resolved {len(resolved_entities)} entities to {len(set(e['resolved_id'] for e in resolved_entities))} unique IDs")
        
    except Exception as e:
        logger.error(f"[PHASE1] Entity resolution failed: {e}")
        # Fallback: use original entities without resolution
        resolved_entities = raw_entities
    
    state["entities"] = resolved_entities
    return state


def common_json_normalization_agent(state: InvestigationState) -> InvestigationState:
    """
    PHASE 1: Normalize all extracted data to common JSON format.
    
    Ensures consistent data structure for downstream processing.
    """
    if state.get("processing_status") == "failed":
        return state
    update_document_progress(state["document_id"], "Normalizing JSON", 68)
    
    try:
        # Normalize entities
        raw_entities = state.get("entities", [])
        normalized_entities = []
        
        for entity in raw_entities:
            try:
                # Convert to format expected by normalizer
                entity_for_normalization = {
                    "type": entity.get("type", "UNKNOWN"),
                    "entity_type": entity.get("type", "UNKNOWN"),
                    "value": entity.get("value", ""),
                    "original_value": entity.get("value", ""),
                    "normalized_value": entity.get("normalized_value", ""),
                    "attributes": entity.get("attributes", {}),
                    "confidence": entity.get("confidence", 1.0),
                    "id": entity.get("resolved_id", entity.get("id")),
                    "status": "EXTRACTED"
                }
                
                # Add provenance from entity
                if "provenance" in entity and isinstance(entity["provenance"], dict):
                    entity_for_normalization["provenance"] = entity["provenance"]
                else:
                    entity_for_normalization["provenance"] = {
                        "document_id": entity.get("document_id", "unknown"),
                        "source_file": entity.get("source_file", "unknown"),
                        "source_type": entity.get("source_type", "unknown"),
                        "extraction_method": entity.get("extraction_method", "unknown"),
                        "confidence": entity.get("confidence", 1.0)
                    }
                
                normalized = normalize_entity_data(entity_for_normalization)
                normalized_entities.append(normalized)
                
            except Exception as e:
                logger.warning(f"[PHASE1] Failed to normalize entity: {e}")
                # Keep original entity if normalization fails
                normalized_entities.append(entity)
        
        state["entities"] = normalized_entities
        logger.info(f"[PHASE1] Normalized {len(normalized_entities)} entities to common JSON format")
        
    except Exception as e:
        logger.error(f"[PHASE1] JSON normalization failed: {e}")
        # Don't fail the workflow, keep original entities
    
    return state


# Relationship label inferred when two *different*-typed entities co-occur in
# the same source record (row/page/line). Used by the generic co-occurrence
# pass below so relationship extraction isn't tied to one fixed CSV schema.
ENTITY_PAIR_RELATIONSHIP = {
    frozenset({"PERSON", "PHONE"}): "USES",
    frozenset({"PERSON", "EMAIL"}): "USES",
    frozenset({"PERSON", "VEHICLE"}): "ASSOCIATED_WITH",
    frozenset({"PERSON", "ORGANIZATION"}): "ASSOCIATED_WITH",
    frozenset({"PERSON", "LOCATION"}): "LOCATED_AT",
    frozenset({"PERSON", "ACCOUNT"}): "ASSOCIATED_WITH",
    frozenset({"PHONE", "LOCATION"}): "OBSERVED_AT",
    frozenset({"VEHICLE", "LOCATION"}): "OBSERVED_AT",
    frozenset({"ORGANIZATION", "LOCATION"}): "LOCATED_AT",
    frozenset({"VEHICLE", "ORGANIZATION"}): "ASSOCIATED_WITH",
}
# Relationship label when two entities of the *same* type co-occur (e.g. two
# phone numbers in one CDR row, two people mentioned in one paragraph).
SAME_TYPE_RELATIONSHIP = {
    "PERSON": "ASSOCIATED_WITH",
    "PHONE": "CALLED",
}


def _field(record: dict, *keys) -> Optional[str]:
    """Fetch the first present, non-null value for any of the candidate keys."""
    for k in keys:
        if k in record and pd.notna(record[k]):
            val = str(record[k]).strip()
            if val:
                return val
    return None


def relationship_extraction_agent(state: InvestigationState) -> InvestigationState:
    if state.get("processing_status") == "failed":
        return state
    update_document_progress(state["document_id"], "Extracting relationships", 70)

    try:
        records = state.get("structured_records", [])
        entities = state.get("entities", [])
        relationships = []
        events = []
        seen_keys = set()

        def add_relationship(source_type, source_val, rel_type, target_type, target_val, evidence_ref, status="POTENTIAL LEAD"):
            if not source_type or not target_type or not source_val or not target_val:
                return
            if source_type == target_type and str(source_val).strip().lower() == str(target_val).strip().lower():
                return  # skip self-relationships
            key = (source_type, str(source_val).strip().lower(), rel_type, target_type, str(target_val).strip().lower())
            if key in seen_keys:
                return
            seen_keys.add(key)
            relationships.append({
                "source_type": source_type, "source_val": str(source_val),
                "relationship": rel_type,
                "target_type": target_type, "target_val": str(target_val),
                "evidence": evidence_ref,
                "status": status
            })

        # --- Pass 1: structured record heuristics ---------------------------
        # Column-name driven extraction for tabular sources (CSV/JSON). Alias
        # lists are broadened (vs. the original literal "caller"/"receiver"
        # names) to match real-world exports such as CDR sheets that use
        # source_a/source_b, calling_number/receiving_number, etc.
        for i, r in enumerate(records):
            if not isinstance(r, dict):
                continue
            evidence_ref = {"document_id": state["document_id"], "file": state["source_file"], "row": i}

            caller = _field(r, "caller", "calling_number", "source_a", "from", "sender")
            receiver = _field(r, "receiver", "receiving_number", "source_b", "to")
            person = _field(r, "person", "person_name", "name", "owner", "customer_name", "caller_name", "subscriber")
            vehicle = _field(r, "vehicle_no", "vehicle_number", "vehicle_id", "registration", "registration_number", "plate")
            organization = _field(r, "organization", "company", "org")
            phone = _field(r, "phone", "contact")
            location = _field(r, "location", "address", "city", "tower")
            timestamp = _field(r, "timestamp", "time", "date", "datetime")

            if caller and receiver:
                add_relationship("PHONE", caller, "CALLED", "PHONE", receiver, evidence_ref)
                if timestamp:
                    event_id = str(uuid4())
                    events.append({"event_id": event_id, "type": "CALL", "timestamp": str(timestamp), "evidence": evidence_ref})
                    add_relationship("PHONE", caller, "INVOLVED_IN", "EVENT", event_id, evidence_ref)
                    if location:
                        add_relationship("EVENT", event_id, "LOCATED_AT", "LOCATION", location, evidence_ref)

            if person and vehicle:
                add_relationship("PERSON", person, "ASSOCIATED_WITH", "VEHICLE", vehicle, evidence_ref)
            if person and organization:
                add_relationship("PERSON", person, "ASSOCIATED_WITH", "ORGANIZATION", organization, evidence_ref)
            if person and phone:
                add_relationship("PERSON", person, "USES", "PHONE", phone, evidence_ref)
            if vehicle and location:
                add_relationship("VEHICLE", vehicle, "OBSERVED_AT", "LOCATION", location, evidence_ref)

        # --- Pass 2: entity co-occurrence ------------------------------------
        # Groups the already-extracted, type-resolved entities by the record
        # they came from (CSV row / TXT line-chunk / PDF page, tracked via
        # provenance.row) and infers relationships between entities that
        # appear together. This is what makes relationship extraction work
        # for unstructured TXT/PDF sources and for CSV schemas that don't
        # match the column aliases above — it relies on the real entities the
        # extractor already found, not on any fixed column layout.
        entities_by_row = defaultdict(list)
        for ent in entities:
            prov = ent.get("provenance") if isinstance(ent.get("provenance"), dict) else {}
            row = prov.get("row", ent.get("row"))
            if row is not None:
                entities_by_row[row].append(ent)

        for row, row_entities in entities_by_row.items():
            evidence_ref = {"document_id": state["document_id"], "file": state["source_file"], "row": row}
            unique = {}
            for ent in row_entities:
                e_type = ent.get("entity_type") or ent.get("type")
                e_val = ent.get("original_value") or ent.get("value")
                if not e_type or not e_val:
                    continue
                e_norm = ent.get("normalized_value") or str(e_val).strip().lower()
                unique[(e_type, e_norm)] = e_val

            items = list(unique.items())
            for a in range(len(items)):
                for b in range(a + 1, len(items)):
                    (type_a, _), val_a = items[a]
                    (type_b, _), val_b = items[b]
                    if type_a == type_b:
                        rel_type = SAME_TYPE_RELATIONSHIP.get(type_a)
                    else:
                        rel_type = ENTITY_PAIR_RELATIONSHIP.get(frozenset({type_a, type_b}))
                    if rel_type:
                        add_relationship(type_a, val_a, rel_type, type_b, val_b, evidence_ref)

        state["relationships"] = relationships
        state["events"] = events
        update_document_progress(
            state["document_id"], "Extracting relationships", 80,
            relationships_found=len(relationships), timeline_events=len(events)
        )
    except Exception as e:
        logger.error(f"[RELATIONSHIPS] Extraction failed for document {state.get('document_id')}: {e}")
        state["relationships"] = state.get("relationships", [])
        state["events"] = state.get("events", [])
        update_document_progress(
            state["document_id"], "Extracting relationships", 80,
            relationships_found=len(state["relationships"]), timeline_events=len(state["events"])
        )
    return state

def _safe_label(raw: str, fallback: str = "ENTITY") -> str:
    """Sanitize a value into a safe Neo4j label/relationship-type identifier
    (Cypher labels can't be parameterized, so this also guards against
    building an invalid or injectable query from unexpected entity types)."""
    label = re.sub(r"[^A-Za-z0-9_]", "_", str(raw or "").strip().upper())
    if not label or not label[0].isalpha():
        label = f"{fallback}_{label}" if label else fallback
    return label


def neo4j_writer_agent(state: InvestigationState) -> InvestigationState:
    if state.get("processing_status") == "failed":
        return state
    update_document_progress(state["document_id"], "Building graph", 90)

    try:
        if neo4j_service.driver is None:
            raise RuntimeError(
                "Neo4j is not reachable (check NEO4J_URI / NEO4J_USERNAME / "
                "NEO4J_PASSWORD and that the database is running). "
                "The graph cannot be persisted."
            )

        # Write Entities. Entities coming out of common_json_normalization_agent
        # use the NormalizedEntity schema (entity_type/original_value), while
        # anything that skipped normalization still uses the older type/value
        # keys — support both so this doesn't KeyError on either shape.
        nodes_written = 0
        for ent in state.get("entities", []):
            entity_type = ent.get("entity_type") or ent.get("type")
            original_value = ent.get("original_value") or ent.get("value")
            if not entity_type or not original_value:
                continue
            normalized_value = ent.get("normalized_value") or normalize_entity_value(entity_type, str(original_value))

            label = _safe_label(entity_type)
            query = f"""
            MERGE (n:{label} {{id: $norm_val}})
            ON CREATE SET n.value = $val, n.type = $type, n.created_at = timestamp()
            RETURN n
            """
            result = neo4j_service.execute_write(query, {
                "norm_val": normalized_value, "val": str(original_value), "type": entity_type
            })
            if result is None:
                raise RuntimeError(f"Failed to write entity node {entity_type}:{original_value} to Neo4j")
            nodes_written += 1

        # Write Events
        for ev in state.get("events", []):
            query = """
            MERGE (n:Event {id: $id})
            ON CREATE SET n.type = $type, n.timestamp = $ts, n.created_at = timestamp()
            """
            neo4j_service.execute_write(query, {"id": ev["event_id"], "type": ev["type"], "ts": ev["timestamp"]})

        # Write Relationships. Endpoint values are normalized with the exact
        # same function used when the entity nodes were created above -
        # previously this re-implemented normalization ad hoc (e.g. phone
        # numbers weren't given the "91" country-code prefix that
        # normalize_entity_value/normalize_phone adds), so the MATCH clauses
        # silently found zero nodes and every relationship was dropped
        # without any error.
        edges_written = 0
        edges_skipped = 0
        for rel in state.get("relationships", []):
            source_type = rel.get("source_type")
            target_type = rel.get("target_type")
            relationship_label = rel.get("relationship")
            if not (source_type and target_type and relationship_label and rel.get("source_val") and rel.get("target_val")):
                edges_skipped += 1
                continue

            src_val = rel["source_val"] if source_type == "EVENT" else normalize_entity_value(source_type, str(rel["source_val"]))
            tgt_val = rel["target_val"] if target_type == "EVENT" else normalize_entity_value(target_type, str(rel["target_val"]))

            query = f"""
            MATCH (a:{_safe_label(source_type)} {{id: $src}})
            MATCH (b:{_safe_label(target_type)} {{id: $tgt}})
            MERGE (a)-[r:{_safe_label(relationship_label, 'REL')}]->(b)
            ON CREATE SET r.evidence_doc = $doc, r.evidence_row = $row, r.status = $status
            RETURN r
            """
            evidence = rel.get("evidence") or {}
            result = neo4j_service.execute_write(query, {
                "src": src_val,
                "tgt": tgt_val,
                "doc": evidence.get("file"),
                "row": evidence.get("row"),
                "status": rel.get("status", "POTENTIAL LEAD")
            })
            if result:
                edges_written += 1
            else:
                edges_skipped += 1
                logger.warning(
                    f"[GRAPH] Could not link relationship (source/target node not found): "
                    f"{source_type}:{rel['source_val']} -{relationship_label}-> {target_type}:{rel['target_val']}"
                )

        logger.info(
            f"[GRAPH] Document {state['document_id']}: wrote {nodes_written} nodes, "
            f"{edges_written} edges ({edges_skipped} relationships skipped/unmatched)"
        )

        evidence_id = create_evidence_record(
            document_id=state["document_id"],
            source_file=state["source_file"],
            source_type=state.get("source_type", "unknown"),
            records_count=len(state.get("structured_records", [])),
            entities_count=len(state.get("entities", [])),
            relationships_count=len(state.get("relationships", [])),
        )

        state["processing_status"] = "completed"
        update_document_progress(
            state["document_id"], "Completed", 100, status="completed", evidence_id=evidence_id
        )
        _audit_processing_event(state, "PROCESSING_COMPLETED", "SUCCESS", {
            "entities": nodes_written, "relationships": edges_written, "evidence_id": evidence_id
        })

    except Exception as e:
        fail_document(state, f"Graph construction failed: {e}", 90)

    return state

# Build the Graph
workflow = StateGraph(InvestigationState)
workflow.add_node("document_router", document_router)
workflow.add_node("csv_preprocessor", csv_preprocessor)
workflow.add_node("json_preprocessor", json_preprocessor)
workflow.add_node("txt_preprocessor", txt_preprocessor)
workflow.add_node("pdf_preprocessor", pdf_preprocessor)
workflow.add_node("normalization_agent", normalization_agent)
workflow.add_node("entity_extraction_agent", entity_extraction_agent)
# PHASE 1: New agents for entity resolution and JSON normalization
workflow.add_node("entity_resolution_agent", entity_resolution_agent)
workflow.add_node("common_json_normalization_agent", common_json_normalization_agent)
workflow.add_node("relationship_extraction_agent", relationship_extraction_agent)
workflow.add_node("neo4j_writer_agent", neo4j_writer_agent)

workflow.add_edge(START, "document_router")
workflow.add_conditional_edges("document_router", route_preprocessor)
workflow.add_edge("csv_preprocessor", "normalization_agent")
workflow.add_edge("json_preprocessor", "normalization_agent")
workflow.add_edge("txt_preprocessor", "normalization_agent")
workflow.add_edge("pdf_preprocessor", "normalization_agent")
workflow.add_edge("normalization_agent", "entity_extraction_agent")
# PHASE 1: Updated workflow with entity resolution and JSON normalization
workflow.add_edge("entity_extraction_agent", "entity_resolution_agent")
workflow.add_edge("entity_resolution_agent", "common_json_normalization_agent")
workflow.add_edge("common_json_normalization_agent", "relationship_extraction_agent")
workflow.add_edge("relationship_extraction_agent", "neo4j_writer_agent")
workflow.add_edge("neo4j_writer_agent", END)

investigation_app = workflow.compile()

def process_document_async(document_id: str, filename: str, uploaded_by: str = "unknown"):
    initial_state = {
        "document_id": document_id,
        "source_file": filename,
        "uploaded_by": uploaded_by,
        "processing_status": "started",
        "processing_progress": 0
    }
    try:
        investigation_app.invoke(initial_state)
    except Exception as e:
        # Safety net: FastAPI BackgroundTasks swallow exceptions silently
        # (they only get printed to the server console), which is what
        # previously left documents stuck at their last progress checkpoint
        # forever with status still "processing". Any unhandled error in any
        # workflow node now always results in a "failed" status the frontend
        # can display and stop polling on.
        logger.exception(f"[WORKFLOW] Unhandled error processing document {document_id}: {e}")
        update_document_progress(
            document_id, "Failed", 90, status="failed",
            error_message=f"Unexpected processing error: {e}"
        )
        _audit_processing_event(
            {"document_id": document_id, "uploaded_by": uploaded_by},
            "PROCESSING_FAILED", "FAILURE", {"error": str(e)}
        )
