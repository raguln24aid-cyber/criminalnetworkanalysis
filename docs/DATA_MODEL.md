# Data Model

Core domain objects, defined in `backend/app/models/domain.py` (SQLAlchemy) and `backend/app/schemas/domain.py` (Pydantic).

## Entities
A person, phone number, location, organization, or other object of interest extracted from case data. Each entity has a stable ID assigned during entity resolution (`backend/app/services/entity_ids.py`, `entity_resolution.py`).

## Relationships
A directed or undirected link between two entities (e.g. "called", "met at", "associated with"), extracted by `relationship_extractor.py` and scored for importance by the intelligence engine.

## Events
A timestamped occurrence tying together one or more entities (e.g. a call, a meeting, a transaction), forming the basis of the temporal graph.

## Evidence
The source artifact (document, call record, statement) an entity/relationship/event was extracted from. Every evidence object is SHA-256 hashed and chained in the evidence ledger (`backend/app/evidence/ledger.py`) for tamper-evidence.

## Graph
Entities and relationships are assembled into a NetworkX graph (`backend/app/services/graph_service.py`), which the intelligence engine (`intelligence_service.py`) analyzes for hidden links, anomalies, contradictions, and node importance.
