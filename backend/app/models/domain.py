from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="INVESTIGATOR")  # ADMIN | INVESTIGATOR
    is_active = Column(Boolean, default=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

class Entity(Base):
    __tablename__ = "entities"
    id = Column(String, primary_key=True, index=True)
    type = Column(String, index=True)  # PERSON, PHONE, VEHICLE, ACCOUNT, LOCATION, ORGANIZATION, EVENT
    name = Column(String)
    attributes = Column(String)  # JSON string

class Relationship(Base):
    __tablename__ = "relationships"
    id = Column(String, primary_key=True, index=True)
    source_id = Column(String, ForeignKey("entities.id"))
    target_id = Column(String, ForeignKey("entities.id"))
    type = Column(String)
    timestamp = Column(String)
    confidence = Column(Float)
    evidence_id = Column(String)
    status = Column(String)  # CONFIRMED, POTENTIAL LEAD, UNVERIFIED, CONTRADICTED

class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(String, primary_key=True, index=True)
    hash = Column(String)
    previous_hash = Column(String, default="")  # chains this record to the one before it
    timestamp = Column(String)
    source = Column(String)
    confidence = Column(Float)
    processing_version = Column(String)
    content = Column(String)  # JSON string of facts

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user = Column(String)
    action = Column(String)
    timestamp = Column(DateTime, default=func.now())
    resource = Column(String)  # deprecated free-text field, kept for compatibility
    result = Column(String)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    details = Column(String, nullable=True)  # JSON string, never secrets/tokens
    correlation_id = Column(String, nullable=True)

class IngestedDocument(Base):
    __tablename__ = "ingested_documents"
    id = Column(String, primary_key=True, index=True)
    source_file = Column(String, index=True)
    source_type = Column(String)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    stage = Column(String, default="uploaded")
    progress = Column(Integer, default=0)
    records_processed = Column(Integer, default=0)
    entities_found = Column(Integer, default=0)
    relationships_found = Column(Integer, default=0)
    timeline_events = Column(Integer, default=0)
    error_message = Column(String, nullable=True)
    processed_file = Column(String, nullable=True)
    evidence_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
