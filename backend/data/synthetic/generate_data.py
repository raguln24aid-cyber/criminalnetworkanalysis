import os
import sys
from sqlalchemy.orm import Session
import json
import hashlib
from datetime import datetime

# Add the parent directory to the path so we can import 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.database import SessionLocal, Base, engine
from app.models.domain import Entity, Relationship, Evidence, AuditLog
from app.evidence.ledger import ledger

def create_synthetic_data():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    entities = [
        {"id": "P001", "type": "PERSON", "name": "Person 001", "attributes": "{}"},
        {"id": "P004", "type": "PERSON", "name": "Person 004", "attributes": "{}"},
        {"id": "P009", "type": "PERSON", "name": "Person 009", "attributes": "{}"},
        {"id": "A007", "type": "ACCOUNT", "name": "Account 007", "attributes": "{}"},
        {"id": "V003", "type": "VEHICLE", "name": "Vehicle 003", "attributes": "{}"},
        {"id": "L001", "type": "LOCATION", "name": "Location 001", "attributes": "{}"},
        {"id": "L008", "type": "LOCATION", "name": "Location 008", "attributes": "{}"}
    ]

    for e in entities:
        db.add(Entity(**e))

    relationships = [
        # Direct relationship P001 -> P004 -> P009 -> A007
        {"id": "R001", "source_id": "P001", "target_id": "P004", "type": "MET", "timestamp": "2026-03-12T10:00:00Z", "confidence": 0.9, "evidence_id": "EV001", "status": "CONFIRMED"},
        {"id": "R002", "source_id": "P004", "target_id": "P009", "type": "CALLED", "timestamp": "2026-03-12T10:15:00Z", "confidence": 0.85, "evidence_id": "EV002", "status": "CONFIRMED"},
        {"id": "R003", "source_id": "P009", "target_id": "A007", "type": "OWNED", "timestamp": "2026-03-12T10:30:00Z", "confidence": 0.6, "evidence_id": "EV003", "status": "UNVERIFIED"},
        
        # Indirect P001 -> V003 -> L008 -> P009
        {"id": "R004", "source_id": "P001", "target_id": "V003", "type": "USED", "timestamp": "2026-03-14T09:00:00Z", "confidence": 0.95, "evidence_id": "EV004", "status": "CONFIRMED"},
        {"id": "R005", "source_id": "V003", "target_id": "L008", "type": "VISITED", "timestamp": "2026-03-14T09:30:00Z", "confidence": 0.99, "evidence_id": "EV005", "status": "CONFIRMED"},
        {"id": "R006", "source_id": "P009", "target_id": "L008", "type": "VISITED", "timestamp": "2026-03-14T09:35:00Z", "confidence": 0.8, "evidence_id": "EV006", "status": "POTENTIAL LEAD"},
        
        # Contradiction data
        {"id": "R007", "source_id": "P001", "target_id": "L001", "type": "VISITED", "timestamp": "2026-03-14T09:30:00Z", "confidence": 0.9, "evidence_id": "EV007", "status": "CONTRADICTED"}
    ]

    for r in relationships:
        db.add(Relationship(**r))

    evidence = [
        {"id": "EV001", "source": "Surveillance_Cam_1", "timestamp": "2026-03-12T10:00:00Z", "confidence": 0.9, "processing_version": "v1.0", "content": '{"fact": "P001 met P004"}'},
        {"id": "EV002", "source": "CDR_Records", "timestamp": "2026-03-12T10:15:00Z", "confidence": 0.85, "processing_version": "v1.0", "content": '{"fact": "P004 called P009"}'},
        {"id": "EV003", "source": "Bank_Statements", "timestamp": "2026-03-12T10:30:00Z", "confidence": 0.6, "processing_version": "v1.0", "content": '{"fact": "P009 associated with A007"}'},
        {"id": "EV004", "source": "Traffic_Cam", "timestamp": "2026-03-14T09:00:00Z", "confidence": 0.95, "processing_version": "v1.0", "content": '{"fact": "P001 used V003"}'},
        {"id": "EV005", "source": "Traffic_Cam", "timestamp": "2026-03-14T09:30:00Z", "confidence": 0.99, "processing_version": "v1.0", "content": '{"fact": "V003 at L008"}'},
        {"id": "EV006", "source": "Witness_Report", "timestamp": "2026-03-14T09:35:00Z", "confidence": 0.8, "processing_version": "v1.0", "content": '{"fact": "P009 at L008"}'},
        {"id": "EV007", "source": "Cell_Tower", "timestamp": "2026-03-14T09:30:00Z", "confidence": 0.9, "processing_version": "v1.0", "content": '{"fact": "P001 at L001"}'}
    ]

    for ev in evidence:
        ev_data = {
            "id": ev["id"],
            "source": ev["source"],
            "timestamp": ev["timestamp"],
            "confidence": ev["confidence"],
            "content": ev["content"]
        }
        ev["hash"] = ledger.create_evidence_hash(ev_data)
        db.add(Evidence(**ev))

    db.commit()
    print("Synthetic data generated successfully.")

if __name__ == "__main__":
    create_synthetic_data()
