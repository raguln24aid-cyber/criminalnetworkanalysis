"""
LLM Entity Extractor for NEXUS-X

Provides LLM-based entity extraction from text using Groq and existing prompts.
Falls back to deterministic extraction when LLM is unavailable.

This service integrates with:
- entity_prompt.py for extraction prompts
- llm_service.py for LLM communication
- entity_extractor.py for deterministic fallback
- entity_resolution.py for entity deduplication
- common_json_normalizer.py for standardized output
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import hashlib

from app.services.llm_service import llm_json
from app.services.entity_extractor import extract_entities_from_record, extract_entities_from_text
from app.services.normalization import normalize_phone, normalize_plate, normalize_email
from app.prompts.entity_prompt import ENTITY_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class LLMEntityExtractor:
    """
    LLM-based entity extractor that uses Groq to extract entities from text.
    
    Features:
    - Extracts entities from structured records (CSV/JSON)
    - Extracts entities from unstructured text (TXT/PDF)
    - Validates and normalizes extracted entities
    - Falls back to deterministic extraction on LLM failure
    - Tracks extraction provenance and confidence
    """
    
    # Entity type mappings for validation
    VALID_ENTITY_TYPES = {
        "PERSON", "PHONE", "EMAIL", "VEHICLE", "NUMBER_PLATE", "LOCATION", 
        "ORGANIZATION", "EVENT", "ACCOUNT", "DEVICE", "TRANSACTION", 
        "IP_ADDRESS", "DOMAIN", "URL", "DATE", "TIME", "DATETIME"
    }
    
    def __init__(self):
        self._llm_available = None  # Cache LLM availability
    
    def _is_llm_available(self) -> bool:
        """Check if LLM service is available."""
        if self._llm_available is None:
            # Test with a simple query
            try:
                from app.services.groq_service import client
                self._llm_available = client is not None
            except:
                self._llm_available = False
        return self._llm_available
    
    def extract_entities_from_text(
        self,
        text: str,
        source_file: str,
        record_id: str = "0",
        field: Optional[str] = None,
        document_id: Optional[str] = None,
        source_type: str = "text"
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Extract entities from plain text using LLM.
        
        Args:
            text: The text to extract entities from
            source_file: Source filename
            record_id: Record identifier (row number, page number, etc.)
            field: Field name if applicable
            document_id: Document ID
            source_type: Source type (csv, json, txt, pdf)
            
        Returns:
            Tuple of (list of extracted entities, was_llm_used)
        """
        if not text or not str(text).strip():
            return [], False
        
        text = str(text).strip()
        use_llm = self._is_llm_available()
        
        # Try LLM extraction first
        if use_llm:
            entities = self._extract_with_llm(
                text, source_file, record_id, field, document_id, source_type
            )
            if entities is not None:
                logger.info(f"[LLM_EXTRACTOR] Extracted {len(entities)} entities from text using LLM")
                return entities, True
        
        # Fallback to deterministic extraction
        logger.info("[LLM_EXTRACTOR] Falling back to deterministic extraction")
        deterministic_entities = extract_entities_from_text(
            text, source_file, record_id, field
        )
        return self._convert_deterministic_entities(deterministic_entities, document_id, source_file, source_type), False
    
    def extract_entities_from_record(
        self,
        record: Dict[str, Any],
        source_file: str,
        record_id: str = "0",
        document_id: Optional[str] = None,
        source_type: str = "csv"
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Extract entities from a structured record using LLM.
        
        Args:
            record: The structured record (dict of field:value)
            source_file: Source filename
            record_id: Record identifier
            document_id: Document ID
            source_type: Source type
            
        Returns:
            Tuple of (list of extracted entities, was_llm_used)
        """
        if not record:
            return [], False
        
        use_llm = self._is_llm_available()
        
        # For structured records, we can use the field names as context
        if use_llm:
            # Convert record to text format for LLM
            record_text = self._record_to_text(record)
            entities = self._extract_with_llm(
                record_text, source_file, record_id, None, document_id, source_type
            )
            if entities is not None:
                logger.info(f"[LLM_EXTRACTOR] Extracted {len(entities)} entities from record using LLM")
                return entities, True
        
        # Fallback to deterministic extraction
        logger.info("[LLM_EXTRACTOR] Falling back to deterministic extraction for record")
        deterministic_entities = extract_entities_from_record(
            record, source_file, record_id
        )
        return self._convert_deterministic_entities(deterministic_entities, document_id, source_file, source_type), False
    
    def _record_to_text(self, record: Dict[str, Any]) -> str:
        """Convert a structured record to text format for LLM processing."""
        lines = []
        for key, value in record.items():
            # `value is not None` doesn't catch pandas NaN (a float) from
            # empty CSV cells - those were leaking through as the literal
            # string "nan" and getting extracted as bogus entity values.
            if value is None or (isinstance(value, float) and value != value):
                continue
            if str(value).strip():
                lines.append(f"{key}: {value}")
        return "\n".join(lines)
    
    def _extract_with_llm(
        self,
        text: str,
        source_file: str,
        record_id: str,
        field: Optional[str],
        document_id: Optional[str],
        source_type: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Internal method to extract entities using LLM.
        
        Returns None if LLM extraction fails.
        """
        try:
            user_prompt = f"""
Extract all entities from the following text. 
Be thorough and precise. Include all possible entity types.

Source: {source_file}
Record: {record_id}
Text: {text}

Return entities in the exact JSON format specified in the system prompt.
"""
            
            result = llm_json(ENTITY_SYSTEM_PROMPT, user_prompt)
            
            if result and "entities" in result:
                entities = result["entities"]
                if isinstance(entities, list):
                    # Validate and normalize entities
                    validated_entities = []
                    for entity in entities:
                        validated = self._validate_llm_entity(entity)
                        if validated:
                            validated_entities.append(self._enrich_entity(
                                validated, source_file, record_id, field, document_id, source_type
                            ))
                    return validated_entities
                else:
                    logger.warning("[LLM_EXTRACTOR] LLM returned non-list entities")
                    return None
            else:
                logger.warning("[LLM_EXTRACTOR] LLM returned no entities or invalid format")
                return None
                
        except Exception as e:
            logger.error(f"[LLM_EXTRACTOR] LLM extraction failed: {e}")
            return None
    
    def _validate_llm_entity(self, entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate an entity extracted by LLM."""
        required_fields = ["entity_type", "original_value"]
        for field in required_fields:
            if field not in entity or not entity[field]:
                logger.warning(f"[LLM_EXTRACTOR] Missing required field {field} in entity")
                return None
        
        # Validate entity type
        entity_type = entity["entity_type"].upper()
        if entity_type not in self.VALID_ENTITY_TYPES:
            logger.warning(f"[LLM_EXTRACTOR] Invalid entity type: {entity_type}")
            # Try to map to valid type
            entity_type = self._map_entity_type(entity_type)
            if entity_type not in self.VALID_ENTITY_TYPES:
                return None
            entity["entity_type"] = entity_type
        
        # Validate confidence
        confidence = entity.get("confidence", 0.9)
        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
            entity["confidence"] = 0.9  # Default confidence for LLM
        
        return entity
    
    def _map_entity_type(self, entity_type: str) -> str:
        """Map entity type aliases to standard types."""
        entity_type = entity_type.upper()
        mappings = {
            "NAME": "PERSON",
            "PERSON_NAME": "PERSON",
            "FULL_NAME": "PERSON",
            "MOBILE": "PHONE",
            "CELL": "PHONE",
            "TELEPHONE": "PHONE",
            "CONTACT": "PHONE",
            "PLATE": "VEHICLE",
            "REGISTRATION": "VEHICLE",
            "CAR": "VEHICLE",
            "ADDRESS": "LOCATION",
            "PLACE": "LOCATION",
            "CITY": "LOCATION",
            "COMPANY": "ORGANIZATION",
            "ORG": "ORGANIZATION",
            "FIRM": "ORGANIZATION",
            "BANK_ACCOUNT": "ACCOUNT",
            "ACCOUNT_NUMBER": "ACCOUNT",
            "WEB": "URL",
            "WEBSITE": "URL",
            "SITE": "URL",
        }
        return mappings.get(entity_type, entity_type)
    
    def _enrich_entity(
        self,
        entity: Dict[str, Any],
        source_file: str,
        record_id: str,
        field: Optional[str],
        document_id: Optional[str],
        source_type: str
    ) -> Dict[str, Any]:
        """Enrich entity with provenance and normalization."""
        entity_type = entity["entity_type"].upper()
        original_value = str(entity["original_value"]).strip()
        
        # Normalize value based on type
        normalized_value = self._normalize_value(entity_type, original_value)
        
        # Generate entity ID
        entity_id = self._generate_entity_id(entity_type, original_value)
        
        return {
            "type": entity_type,
            "value": original_value,
            "normalized_value": normalized_value,
            "id": entity_id,
            "confidence": entity.get("confidence", 0.9),
            "source_text": entity.get("source_text", original_value),
            "page": entity.get("page"),
            "row": int(record_id) if record_id.isdigit() else None,
            "field": field,
            "document_id": document_id or "unknown",
            "source_file": source_file,
            "source_type": source_type,
            "extraction_method": "llm"
        }
    
    def _normalize_value(self, entity_type: str, value: str) -> str:
        """Normalize value based on entity type."""
        if entity_type in ["PHONE", "CELL", "MOBILE", "TELEPHONE", "CONTACT"]:
            return normalize_phone(value)
        elif entity_type in ["VEHICLE", "PLATE", "REGISTRATION", "CAR"]:
            return normalize_plate(value)
        elif entity_type in ["EMAIL", "MAIL"]:
            return normalize_email(value)
        else:
            return value.strip().lower()
    
    def _generate_entity_id(self, entity_type: str, value: str) -> str:
        """Generate deterministic entity ID."""
        from app.services.entity_ids import entity_id
        return entity_id(entity_type, value)
    
    def _convert_deterministic_entities(
        self,
        deterministic_entities: List[Dict[str, Any]],
        document_id: Optional[str],
        source_file: str,
        source_type: str
    ) -> List[Dict[str, Any]]:
        """Convert deterministic entity format to our format."""
        converted = []
        for entity in deterministic_entities:
            entity_type = entity.get("type", "UNKNOWN").upper()
            value = entity.get("value", "")
            field = entity.get("field")
            
            converted.append({
                "type": entity_type,
                "value": value,
                "normalized_value": entity.get("normalized_value", value.lower()),
                "id": self._generate_entity_id(entity_type, value),
                "confidence": 1.0,  # Deterministic extraction is confident
                "source_text": value,
                "page": None,
                "row": entity.get("record_id"),
                "field": field,
                "document_id": document_id or "unknown",
                "source_file": source_file,
                "source_type": source_type,
                "extraction_method": "deterministic"
            })
        return converted


# Global extractor instance
extractor = LLMEntityExtractor()


def extract_entities_llm(
    text: str,
    source_file: str,
    record_id: str = "0",
    field: Optional[str] = None,
    document_id: Optional[str] = None,
    source_type: str = "text"
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Convenience function to extract entities from text using LLM.
    
    Returns tuple of (entities, was_llm_used).
    """
    return extractor.extract_entities_from_text(
        text, source_file, record_id, field, document_id, source_type
    )


def extract_entities_llm_record(
    record: Dict[str, Any],
    source_file: str,
    record_id: str = "0",
    document_id: Optional[str] = None,
    source_type: str = "csv"
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Convenience function to extract entities from record using LLM.
    
    Returns tuple of (entities, was_llm_used).
    """
    return extractor.extract_entities_from_record(
        record, source_file, record_id, document_id, source_type
    )


def batch_extract_entities_llm(
    records: List[Dict[str, Any]],
    source_file: str,
    document_id: Optional[str] = None,
    source_type: str = "csv"
) -> List[Dict[str, Any]]:
    """
    Extract entities from multiple records using LLM.
    
    Args:
        records: List of records
        source_file: Source filename
        document_id: Document ID
        source_type: Source type
        
    Returns:
        List of all extracted entities
    """
    all_entities = []
    for i, record in enumerate(records):
        entities, _ = extractor.extract_entities_from_record(
            record, source_file, str(i), document_id, source_type
        )
        all_entities.extend(entities)
    return all_entities
