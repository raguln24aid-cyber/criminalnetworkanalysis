from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Request, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.domain import UserCreate, Token, CopilotQuery
from app.models.domain import User, Entity, Relationship, Evidence, AuditLog, IngestedDocument
from app.security.auth import (
    get_password_hash, verify_password, create_access_token,
    MAX_FAILED_ATTEMPTS, LOCKOUT_MINUTES,
)
from app.security.deps import get_current_user, require_role
from app.services.graph_service import GraphService
from app.services.intelligence_service import IntelligenceService
from app.services.groq_service import query_copilot
from app.services.workflow_service import process_document_async
from app.services.audit_service import log_action
from app.evidence.ledger import ledger
from app.config import get_settings
from pathlib import Path
from uuid import uuid4
import pandas as pd

settings = get_settings()
ALLOWED_EXTENSIONS = {".csv", ".json", ".txt", ".pdf"}
UPLOAD_FOLDER = Path(__file__).resolve().parent.parent.parent / settings.UPLOAD_DIR
MAX_FILE_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def sanitize_filename(filename: str) -> str:
    basename = Path(filename).name
    stem = Path(basename).stem
    suffix = Path(basename).suffix.lower()
    safe_stem = "".join(c for c in stem if c.isalnum() or c in "._- ").strip("._- ")
    if not safe_stem:
        safe_stem = f"upload_{uuid4().hex[:8]}"
    return f"{safe_stem}{suffix}" if suffix in ALLOWED_EXTENSIONS else safe_stem

router = APIRouter()

@router.post("/auth/login")
def login(user: UserCreate, request: Request, db: Session = Depends(get_db)):
    # Real authentication: accounts are provisioned ahead of time (see
    # backend/scripts/create_admin.py) - a login attempt for a username that
    # doesn't exist can no longer silently create one. Previously ANY
    # username/password typed into the login form was auto-registered as a
    # valid account on first use, so the login screen was not actually a gate.
    generic_error = HTTPException(status_code=401, detail="Incorrect username or password")
    db_user = db.query(User).filter(User.username == user.username).first()

    if not db_user:
        # Same generic error as a wrong password - don't reveal whether the
        # username exists.
        log_action(db, user.username, "LOGIN", "auth", result="FAILURE",
                   details={"reason": "unknown_username", "ip": request.client.host if request.client else None})
        raise generic_error

    if not db_user.is_active:
        log_action(db, user.username, "LOGIN", "auth", result="FAILURE",
                   details={"reason": "account_disabled"})
        raise HTTPException(status_code=403, detail="This account has been disabled.")

    if db_user.locked_until and db_user.locked_until > datetime.utcnow():
        remaining = int((db_user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
        log_action(db, user.username, "LOGIN", "auth", result="FAILURE",
                   details={"reason": "account_locked"})
        raise HTTPException(status_code=403, detail=f"Account locked from too many failed attempts. Try again in {remaining} minute(s).")

    if not verify_password(user.password, db_user.hashed_password):
        db_user.failed_login_attempts = (db_user.failed_login_attempts or 0) + 1
        locked_now = db_user.failed_login_attempts >= MAX_FAILED_ATTEMPTS
        if locked_now:
            db_user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
            db_user.failed_login_attempts = 0
        db.commit()
        log_action(db, user.username, "LOGIN", "auth", result="FAILURE",
                   details={"reason": "bad_password", "account_locked": locked_now})
        raise generic_error

    # Success
    db_user.failed_login_attempts = 0
    db_user.locked_until = None
    db.commit()

    access_token = create_access_token(data={"sub": db_user.username, "role": db_user.role})
    log_action(db, db_user.username, "LOGIN", "auth", result="SUCCESS")
    return {"access_token": access_token, "token_type": "bearer", "role": db_user.role, "username": db_user.username}


@router.post("/auth/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # JWTs are stateless here - there is no server-side session to revoke, so
    # this exists to produce a real audit trail entry. The frontend still
    # discards the token client-side; a token already issued remains
    # cryptographically valid until it expires (see ACCESS_TOKEN_EXPIRE_MINUTES).
    log_action(db, current_user.username, "LOGOUT", "auth", result="SUCCESS")
    return {"message": "Logged out"}


@router.post("/auth/refresh")
def refresh_token(current_user: User = Depends(get_current_user)):
    # Sliding-session refresh: requires a still-valid (unexpired) access token
    # and issues a new one with a fresh expiry. This is a deliberately simpler
    # alternative to a separate long-lived refresh-token store (which would
    # need its own revocation/rotation table) - acceptable for this stage
    # because the access-token lifetime is short; a stronger separate
    # refresh-token design is flagged as follow-up hardening.
    new_token = create_access_token(data={"sub": current_user.username, "role": current_user.role})
    return {"access_token": new_token, "token_type": "bearer", "role": current_user.role, "username": current_user.username}


@router.get("/auth/me")
def read_current_user(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "role": current_user.role}

@router.post("/data/upload")
async def upload_data(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please upload CSV, JSON, TXT, or PDF files.",
        )

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File is too large. Maximum size is 50 MB.",
        )

    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

    safe_name = sanitize_filename(file.filename)
    dest = UPLOAD_FOLDER / safe_name
    if dest.exists():
        stem = Path(safe_name).stem
        suffix = Path(safe_name).suffix
        safe_name = f"{stem}_{uuid4().hex[:8]}{suffix}"
        dest = UPLOAD_FOLDER / safe_name

    dest.write_bytes(contents)

    # Save initial state in DB
    doc_id = str(uuid4())
    db = next(get_db())
    new_doc = IngestedDocument(
        id=doc_id,
        source_file=safe_name,
        source_type=extension.replace(".", ""),
        status="processing",
        stage="Uploaded",
        progress=0
    )
    db.add(new_doc)
    db.commit()

    log_action(db, current_user.username, "UPLOAD", "document", doc_id, result="SUCCESS",
               details={"filename": safe_name, "size_bytes": len(contents)})

    # Trigger async LangGraph processing
    background_tasks.add_task(process_document_async, doc_id, safe_name, current_user.username)

    return {
        "success": True,
        "document_id": doc_id,
        "filename": safe_name,
        "message": "File uploaded and processing started"
    }

@router.get("/processing/{document_id}")
def get_processing_status(document_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(IngestedDocument).filter(IngestedDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {
        "document_id": doc.id,
        "status": doc.status,
        "stage": doc.stage,
        "progress": doc.progress,
        "records_processed": doc.records_processed,
        "entities_found": doc.entities_found,
        "relationships_found": doc.relationships_found,
        "events_found": doc.timeline_events,
        "error": doc.error_message,
        "evidence_id": doc.evidence_id
    }

@router.get("/evidence")
def list_evidence(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    records = db.query(Evidence).order_by(Evidence.timestamp.desc()).all()
    return [
        {"id": e.id, "source": e.source, "timestamp": e.timestamp, "confidence": e.confidence}
        for e in records
    ]

@router.get("/entities")
def get_entities(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.neo4j_db import neo4j_service
    cypher = """
    MATCH (n)
    WHERE NOT n:Event
    RETURN n
    """
    results = neo4j_service.execute_read(cypher)
    entities = []
    if results:
        for res in results:
            n = res.get("n")
            # execute_read serializes each Neo4j Node via record.data(), which
            # returns a plain dict of its properties (no .labels attribute) -
            # use the "type" property every entity node is written with
            # instead of trying to introspect Cypher labels here.
            if n:
                entities.append({
                    "id": n.get("id"),
                    "type": n.get("type", "Unknown"),
                    "name": n.get("value", n.get("id")),
                    "attributes": "{}"
                })
    return entities

@router.get("/graph")
def get_graph(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # The ingestion pipeline (workflow_service.neo4j_writer_agent) persists the
    # knowledge graph to Neo4j, not to the SQL Entity/Relationship tables that
    # GraphService reads from (nothing in the app ever writes to those SQL
    # tables) - reading from SQL here always returned an empty graph to the
    # Network Explorer regardless of how ingestion went. Read from Neo4j
    # instead, the same store the graph is actually written to.
    from app.neo4j_db import neo4j_service

    if neo4j_service.driver is None:
        raise HTTPException(
            status_code=503,
            detail="Neo4j is not reachable. Check NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD and that the database is running.",
        )

    nodes_cypher = "MATCH (n) RETURN n"
    node_results = neo4j_service.execute_read(nodes_cypher) or []
    nodes = []
    seen_ids = set()
    for res in node_results:
        n = res.get("n")
        if not n:
            continue
        node_id = n.get("id")
        if node_id is None or node_id in seen_ids:
            continue
        seen_ids.add(node_id)
        # execute_read serializes each Neo4j Node via record.data(), which
        # returns a plain dict of its properties (no .labels attribute) - use
        # the "type" property every entity/event node is written with instead
        # of trying to introspect Cypher labels here.
        nodes.append({
            "id": node_id,
            "type": n.get("type", "UNKNOWN"),
            "name": n.get("value", node_id),
        })

    edges_cypher = """
    MATCH (a)-[r]->(b)
    RETURN a.id AS source, b.id AS target, type(r) AS type,
           r.status AS status, r.evidence_doc AS evidence_doc, r.evidence_row AS evidence_row
    """
    edge_results = neo4j_service.execute_read(edges_cypher) or []
    edges = []
    for res in edge_results:
        if res.get("source") is None or res.get("target") is None:
            continue
        edges.append({
            "id": f"{res['source']}_{res['type']}_{res['target']}",
            "source": res["source"],
            "target": res["target"],
            "type": res["type"],
            "status": res.get("status") or "POTENTIAL LEAD",
            "evidence": {"file": res.get("evidence_doc"), "row": res.get("evidence_row")},
        })

    return {"nodes": nodes, "links": edges}

@router.get("/intelligence/hidden-links")
def get_hidden_links(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = IntelligenceService(db)
    return service.get_hidden_links()

@router.get("/intelligence/anomalies")
def get_anomalies(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = IntelligenceService(db)
    return service.get_anomalies()

@router.get("/intelligence/contradictions")
def get_contradictions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = IntelligenceService(db)
    return service.get_contradictions()

@router.get("/intelligence/important-nodes")
def get_important_nodes(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = IntelligenceService(db)
    return service.get_important_nodes()

@router.get("/investigation/priorities")
def get_priorities(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = IntelligenceService(db)
    return service.get_investigation_priorities()

@router.get("/evidence/chain/verify")
def verify_evidence_chain(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Registered before /evidence/{id}/verify so "chain" isn't swallowed as
    # a literal evidence id by that route.
    result = ledger.verify_chain(db)
    log_action(db, current_user.username, "VERIFY_EVIDENCE_CHAIN", "evidence_chain",
               result="SUCCESS" if result.get("status") == "VALID" else "TAMPER_DETECTED",
               details={"length": result.get("length"), "broken_at": result.get("broken_at")})
    return result

@router.get("/evidence/{id}/verify")
def verify_evidence(id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    is_valid = ledger.verify_integrity(db, id)
    log_action(db, current_user.username, "VERIFY_EVIDENCE", "evidence", id,
               result="SUCCESS" if is_valid else "TAMPER_DETECTED")
    return {"status": "VALID" if is_valid else "TAMPER DETECTED"}

def _extract_document_text(file_path: Path, source_type: str, max_chars: int = 1200) -> str:
    """Read back the actual text of an uploaded document (reusing the same
    parsers workflow_service.py uses) so the Copilot can quote/reason over
    what a report literally says, not just the entities/relationships
    extracted from it."""
    try:
        if source_type == "csv":
            text = pd.read_csv(file_path).to_string(index=False)
        elif source_type in ("json", "txt"):
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        elif source_type == "pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(file_path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            text = ""
    except Exception as e:
        text = f"[Could not read {file_path.name}: {e}]"
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...[truncated]"
    return text


def _build_case_context(db: Session, query: str = "", max_relationships: int = 100, max_doc_chars: int = 1200, max_total_chars: int = 8000):
    """Builds the Copilot's context using real Graph RAG retrieval:

    1. Query-aware retrieval first (app.services.graph_rag) - searches Neo4j
       for entities named in the question and pulls their FULL neighborhood.
       This section is placed first and is what the truncation below
       protects, so an entity's real connections can no longer silently miss
       the cut just because Neo4j happened to return them late in an
       unordered scan.
    2. A general graph overview (broad entity/relationship sample) as
       supplementary situational context.
    3. Raw text of recently completed documents, so the Copilot can quote a
       report directly, not just graph facts.

    Still capped in total size - the Groq free tier rejects oversized
    requests outright (HTTP 413), separately from its per-minute token
    budget - but the cap now trims the least-relevant tail content instead
    of chopping the answer to the actual question."""
    from app.neo4j_db import neo4j_service
    from app.services.graph_rag import retrieve_relevant_subgraph

    sections = []
    evidence_sources = []

    if query:
        targeted_context, targeted_sources = retrieve_relevant_subgraph(query)
        if targeted_context:
            sections.append(targeted_context)
            evidence_sources.extend(targeted_sources)

    if neo4j_service.driver is not None:
        node_results = neo4j_service.execute_read("MATCH (n) RETURN n") or []
        entities_by_id = {}
        for res in node_results:
            n = res.get("n")
            if not n or n.get("id") is None:
                continue
            entities_by_id[n["id"]] = f"{n.get('type', 'UNKNOWN')} \"{n.get('value', n['id'])}\""

        if entities_by_id:
            lines = [f"- {v} (id={k})" for k, v in list(entities_by_id.items())[:100]]
            sections.append("KNOWN ENTITIES (from the case graph):\n" + "\n".join(lines))

        edge_results = neo4j_service.execute_read("""
            MATCH (a)-[r]->(b)
            RETURN a.id AS source, a.type AS source_type, a.value AS source_value,
                   b.id AS target, b.type AS target_type, b.value AS target_value,
                   type(r) AS rel_type, r.evidence_doc AS doc, r.evidence_row AS row, r.status AS status
        """) or []

        if edge_results:
            lines = []
            for e in edge_results[:max_relationships]:
                doc = e.get("doc")
                if doc:
                    evidence_sources.append(doc)
                lines.append(
                    f"- {e.get('source_type')} \"{e.get('source_value')}\" "
                    f"-[{e.get('rel_type')}]-> {e.get('target_type')} \"{e.get('target_value')}\" "
                    f"(status={e.get('status')}, evidence={doc}#row{e.get('row')})"
                )
            sections.append("KNOWN RELATIONSHIPS (from the case graph):\n" + "\n".join(lines))

    if not sections:
        sections.append("KNOWN ENTITIES: none yet - no uploaded documents have finished processing.")

    # Most recent 5 completed documents only - enough to ground answers in
    # the actual report text without ballooning the request past Groq's
    # per-request size limit as more files get uploaded over a session.
    docs = (
        db.query(IngestedDocument)
        .filter(IngestedDocument.status == "completed")
        .order_by(IngestedDocument.updated_at.desc())
        .limit(5)
        .all()
    )
    for doc in docs:
        file_path = UPLOAD_FOLDER / doc.source_file
        if not file_path.exists():
            continue
        text = _extract_document_text(file_path, doc.source_type, max_doc_chars)
        if text:
            sections.append(f"SOURCE DOCUMENT '{doc.source_file}':\n{text}")
            evidence_sources.append(doc.source_file)

    context = "\n\n".join(sections)
    if len(context) > max_total_chars:
        context = context[:max_total_chars] + "\n...[context truncated to fit request size limits]"
    return context, sorted(set(evidence_sources))


@router.post("/copilot/query")
def copilot_query(query: CopilotQuery, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not query.query or not query.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")
    context, evidence_sources = _build_case_context(db, query=query.query)
    result = query_copilot(query.query, context)
    # Cite the real documents/relationships behind the answer instead of the
    # generic "Extracted from context" placeholder.
    if evidence_sources:
        result["evidence"] = evidence_sources
    log_action(db, current_user.username, "COPILOT_QUERY", "copilot", result="SUCCESS",
               details={"question": query.query[:200]})
    return result

@router.get("/audit")
def get_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN")),
    user: str = None,
    action: str = None,
    resource_type: str = None,
    limit: int = 200,
    offset: int = 0,
):
    # Admin-only: ordinary investigators can't view or (via any endpoint -
    # there is no update/delete route for this table at all) alter the log.
    q = db.query(AuditLog)
    if user:
        q = q.filter(AuditLog.user == user)
    if action:
        q = q.filter(AuditLog.action == action)
    if resource_type:
        q = q.filter(AuditLog.resource_type == resource_type)
    total = q.count()
    rows = q.order_by(AuditLog.timestamp.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 500)).all()
    return {"total": total, "results": rows}
