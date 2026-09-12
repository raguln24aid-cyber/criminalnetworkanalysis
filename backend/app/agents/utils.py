import logging
from pathlib import Path

from app.config import get_settings
from app.database import SessionLocal
from app.models.domain import IngestedDocument

settings = get_settings()
logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_FOLDER = BACKEND_ROOT / settings.UPLOAD_DIR
PROCESSED_FOLDER = BACKEND_ROOT / settings.PROCESSED_DIR


def upload_path(filename: str) -> Path:
    return UPLOAD_FOLDER / filename


def update_document_progress(document_id: str, stage: str, progress: int, status: str = "processing", **kwargs):
    db = SessionLocal()
    try:
        doc = db.query(IngestedDocument).filter(IngestedDocument.id == document_id).first()
        if doc:
            doc.stage = stage
            doc.progress = progress
            doc.status = status
            for key, value in kwargs.items():
                setattr(doc, key, value)
            db.commit()
            logger.info("[LANGGRAPH] doc=%s stage=%s progress=%s status=%s", document_id, stage, progress, status)
    finally:
        db.close()


def mark_failed(document_id: str, stage: str, error: str):
    update_document_progress(document_id, stage, 0, status="failed", error_message=error)


def append_stage(state: dict, stage: str) -> list:
    stages = list(state.get("stages_completed") or [])
    if stage not in stages:
        stages.append(stage)
    return stages
