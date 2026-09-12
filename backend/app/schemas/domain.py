from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    # Note: this schema is also used for the login request body. Login only
    # ever checks a pre-existing account's actual stored role - a client
    # can't self-assign a role by putting one in the request (see
    # /auth/login in endpoints.py, which never reads this field).
    role: str = "INVESTIGATOR"

    @field_validator("username")
    @classmethod
    def username_reasonable(cls, v):
        v = (v or "").strip()
        if not (1 <= len(v) <= 50):
            raise ValueError("Username must be 1-50 characters.")
        return v

    @field_validator("password")
    @classmethod
    def password_not_absurd(cls, v):
        # Deliberately not enforcing a minimum length here: this schema also
        # carries login requests, and rejecting a short password at that
        # boundary would leak "your password is too short to be a real
        # account" before the generic incorrect-credentials check runs.
        # Minimum length is enforced at account-creation time instead (see
        # backend/scripts/create_admin.py).
        if len(v) > 256:
            raise ValueError("Password is too long.")
        return v

class Token(BaseModel):
    access_token: str
    token_type: str

class Entity(BaseModel):
    id: str
    type: str
    name: str
    attributes: Dict[str, Any]

class Relationship(BaseModel):
    id: str
    source_id: str
    target_id: str
    type: str
    timestamp: str
    confidence: float
    evidence_id: str
    status: str

class Evidence(BaseModel):
    id: str
    hash: str
    timestamp: str
    source: str
    confidence: float
    processing_version: str
    content: str

class CopilotQuery(BaseModel):
    query: str
    context: Optional[str] = None

class ProcessingStatus(BaseModel):
    document_id: str
    status: str
    progress: int
    stage: str
    source_file: Optional[str] = None
    records_processed: Optional[int] = None
    entities_found: Optional[int] = None
    relationships_found: Optional[int] = None
    timeline_events: Optional[int] = None
    error_message: Optional[str] = None
    stages_completed: Optional[List[str]] = None
