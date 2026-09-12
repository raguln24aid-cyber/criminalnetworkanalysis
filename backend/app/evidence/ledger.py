import hashlib
import json


class LocalHashChainLedger:
    """
    Tamper-evident ledger for processed evidence.

    Each Evidence record's hash is computed over its own fields *plus* the
    hash of the record immediately before it (previous_hash) - the same
    linking scheme a blockchain or git commit chain uses. That has two
    consequences a per-record-only hash can't give you:

    - Editing any single record changes its hash, which breaks every
      record chained after it, not just that one - tampering anywhere in
      the history is visible from a single check at the end of the chain.
    - Deleting or reordering a whole record is also detectable: the next
      record's stored previous_hash will no longer match the hash of
      whatever now precedes it.

    (Previously create_evidence_hash's previous_hash parameter existed but
    was never actually passed by any caller, so every record was hashed in
    isolation with previous_hash="" - no chain existed despite the class
    name.)
    """

    def create_evidence_hash(self, evidence_data: dict, previous_hash: str = "") -> str:
        data_string = json.dumps(evidence_data, sort_keys=True)
        return hashlib.sha256(f"{data_string}{previous_hash}".encode()).hexdigest()

    def get_latest_hash(self, db) -> str:
        """Hash of the most recently created evidence record, or "" if the
        chain is empty (genesis)."""
        from app.models.domain import Evidence
        latest = db.query(Evidence).order_by(Evidence.timestamp.desc()).first()
        return latest.hash if latest else ""

    def _record_fields(self, evidence) -> dict:
        return {
            "id": evidence.id,
            "source": evidence.source,
            "timestamp": evidence.timestamp,
            "confidence": evidence.confidence,
            "content": evidence.content,
        }

    def verify_integrity(self, db, evidence_id: str) -> bool:
        """Verifies a single record's own fields haven't been altered,
        using whatever previous_hash it was originally chained to."""
        from app.models.domain import Evidence
        evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        if not evidence:
            return False

        computed_hash = self.create_evidence_hash(
            self._record_fields(evidence), evidence.previous_hash or ""
        )
        return computed_hash == evidence.hash

    def verify_chain(self, db) -> dict:
        """
        Verifies the entire evidence chain: every record's own fields, and
        that every record's previous_hash actually matches the hash of the
        record before it. Returns where the chain broke (if anywhere) so
        the UI can point at the exact evidence ID that failed.
        """
        from app.models.domain import Evidence
        records = db.query(Evidence).order_by(Evidence.timestamp.asc()).all()

        if not records:
            return {"status": "VALID", "length": 0, "broken_at": None, "reason": None}

        expected_previous_hash = ""
        for record in records:
            if (record.previous_hash or "") != expected_previous_hash:
                return {
                    "status": "BROKEN",
                    "length": len(records),
                    "broken_at": record.id,
                    "reason": "This record's previous_hash doesn't match the hash of the record before it "
                              "(a record was likely inserted, deleted, or reordered).",
                }

            recomputed = self.create_evidence_hash(self._record_fields(record), record.previous_hash or "")
            if recomputed != record.hash:
                return {
                    "status": "BROKEN",
                    "length": len(records),
                    "broken_at": record.id,
                    "reason": "This record's own fields don't match its stored hash (the record was edited "
                              "after creation).",
                }

            expected_previous_hash = record.hash

        return {"status": "VALID", "length": len(records), "broken_at": None, "reason": None}


ledger = LocalHashChainLedger()
