# API Reference

Base URL (local dev): `http://localhost:8000`

## Auth
| Method | Path | Description |
|---|---|---|
| POST | `/auth/login` | Authenticate and receive a JWT |
| POST | `/auth/logout` | Invalidate the current session |
| POST | `/auth/refresh` | Refresh an access token |
| GET | `/auth/me` | Get the current authenticated user |

## Data Ingestion
| Method | Path | Description |
|---|---|---|
| POST | `/data/upload` | Upload a case file for extraction |
| GET | `/processing/{document_id}` | Check ingestion/processing status |

## Evidence & Entities
| Method | Path | Description |
|---|---|---|
| GET | `/evidence` | List evidence objects |
| GET | `/entities` | List extracted entities |
| GET | `/graph` | Get the full temporal graph |
| GET | `/evidence/chain/verify` | Verify the entire evidence ledger's integrity |
| GET | `/evidence/{id}/verify` | Verify a single evidence item's hash |

## Intelligence
| Method | Path | Description |
|---|---|---|
| GET | `/intelligence/hidden-links` | Discover non-obvious connections |
| GET | `/intelligence/anomalies` | Behavioral anomalies in the network |
| GET | `/intelligence/contradictions` | Conflicting evidence/statements |
| GET | `/intelligence/important-nodes` | Structurally important entities |
| GET | `/investigation/priorities` | IIG-ranked next investigative steps |

## Copilot & Audit
| Method | Path | Description |
|---|---|---|
| POST | `/copilot/query` | Ask a natural language question over the graph |
| GET | `/audit` | List audit log entries |

See `backend/app/api/endpoints.py` for full request/response schemas.
