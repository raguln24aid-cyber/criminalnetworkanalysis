from typing import Any, List, Optional, TypedDict


class InvestigationState(TypedDict, total=False):
    case_id: str
    document_id: str
    file_path: str
    file_name: str
    file_type: str
    source_file: str
    source_type: str

    raw_content: Any
    normalized_data: Any
    structured_records: list
    chunks: list

    entities: list
    events: list
    locations: list
    relationships: list
    resolved_entities: list

    evidence: list
    provenance: list
    common_json: dict

    neo4j_result: dict
    graph_analysis: dict
    investigation_suggestions: list

    processing_stage: str
    processing_progress: int
    processing_status: str
    stages_completed: list
    errors: list

    records_processed: int
    entities_found: int
    relationships_found: int
    timeline_events: int
    ocr_required: bool
