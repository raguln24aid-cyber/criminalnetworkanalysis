# Architecture

## Overview
NEXUS-X ingests fragmented case data (documents, call records, statements), extracts entities and relationships with an LLM pipeline, and stores them as a temporal graph that investigators can query and visualize.

## Data Flow
1. **Ingestion** (`backend/app/api/endpoints.py` → `/data/upload`) — raw files are accepted and handed to the agent workflow.
2. **Extraction** (`backend/app/agents/`, `backend/app/services/entity_extractor.py`, `relationship_extractor.py`) — an LLM (via `groq_service.py`) pulls entities, relationships, and events from unstructured text using prompt templates in `backend/app/prompts/`.
3. **Normalization & Resolution** (`common_json_normalizer.py`, `normalization.py`, `entity_resolution.py`, `entity_ids.py`) — extracted objects are cleaned, deduplicated, and assigned stable IDs.
4. **Evidence Ledger** (`backend/app/evidence/ledger.py`) — every piece of evidence is hashed (SHA-256) for tamper-evidence and chained for integrity verification.
5. **Graph Construction** (`backend/app/services/graph_service.py`) — entities and relationships are assembled into a NetworkX graph, persisted via SQLAlchemy models (`backend/app/models/domain.py`).
6. **Intelligence Engine** (`intelligence_service.py`) — computes node importance, hidden links, anomalies, contradictions, and IIG (Investigation Information Gain) ranking over the graph.
7. **Investigation Copilot** (`graph_rag.py`, `/copilot/query`) — answers natural language questions using retrieval over the graph plus the LLM.
8. **Frontend** (`frontend/src/pages/`) — React pages consume these APIs: Command Center, Network Explorer, Evidence Explorer, Intelligence, Copilot, Data Ingestion, Audit Logs.

## Cross-Cutting Concerns
- **Auth**: JWT-based (`backend/app/security/`), enforced via FastAPI dependencies.
- **Audit**: All investigator actions are logged (`backend/app/services/audit_service.py`) and viewable in the Audit Logs page.
- **Deployment**: Dockerized services behind Caddy (`deploy/`), with a systemd unit for the backend in production.
