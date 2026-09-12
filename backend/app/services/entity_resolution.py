"""
Entity Resolution Service for NEXUS-X

Provides cross-document entity deduplication and consistent ID generation.
Uses the existing entity_ids.py for deterministic ID generation.

This service ensures that the same entity (e.g., "John Doe" or "+919876543210")
receives the same ID across all documents and processing runs.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import threading

from app.services.entity_ids import entity_id, normalize_entity_value

logger = logging.getLogger(__name__)


@dataclass
class ResolvedEntity:
    """A resolved entity with consistent ID and provenance."""
    entity_type: str
    original_value: str
    normalized_value: str
    resolved_id: str
    confidence: float = 1.0
    provenance: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.entity_type,
            "value": self.original_value,
            "normalized_value": self.normalized_value,
            "id": self.resolved_id,
            "confidence": self.confidence,
            "provenance": self.provenance
        }


class EntityResolver:
    """
    Thread-safe entity resolver that maintains a registry of seen entities
    across documents to ensure consistent ID generation.
    
    Usage:
        resolver = EntityResolver()
        resolved = resolver.resolve("PERSON", "John Doe", {"document_id": "doc1", "row": 1})
        # Later in another document
        resolved2 = resolver.resolve("PERSON", "John Doe", {"document_id": "doc2", "row": 5})
        # resolved.resolved_id == resolved2.resolved_id
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._entity_registry: Dict[Tuple[str, str], ResolvedEntity] = {}
        # Index by normalized value for fast lookup
        self._normalized_index: Dict[Tuple[str, str], str] = {}
    
    def _get_normalized_key(self, entity_type: str, value: str) -> Tuple[str, str]:
        """Get a normalized key for entity lookup."""
        normalized = normalize_entity_value(entity_type, value)
        return (entity_type.upper(), normalized)
    
    def resolve(
        self, 
        entity_type: str, 
        value: str, 
        provenance: Optional[Dict[str, Any]] = None
    ) -> ResolvedEntity:
        """
        Resolve an entity to a consistent ID.
        
        If the entity has been seen before (same type + normalized value),
        returns the existing ResolvedEntity with updated provenance.
        Otherwise, creates a new ResolvedEntity with a generated ID.
        
        Args:
            entity_type: The type of entity (PERSON, PHONE, VEHICLE, etc.)
            value: The original value of the entity
            provenance: Provenance information (document_id, file, row, etc.)
            
        Returns:
            ResolvedEntity with consistent ID and combined provenance
        """
        if not value or not str(value).strip():
            raise ValueError(f"Cannot resolve empty value for type {entity_type}")
        
        entity_type_upper = entity_type.upper()
        original_value = str(value).strip()
        normalized_value = normalize_entity_value(entity_type_upper, original_value)
        lookup_key = (entity_type_upper, normalized_value)
        
        with self._lock:
            if lookup_key in self._entity_registry:
                existing = self._entity_registry[lookup_key]
                if provenance:
                    existing.provenance.append(provenance)
                return existing
            else:
                resolved_id = entity_id(entity_type_upper, original_value)
                new_entity = ResolvedEntity(
                    entity_type=entity_type_upper,
                    original_value=original_value,
                    normalized_value=normalized_value,
                    resolved_id=resolved_id,
                    provenance=[provenance] if provenance else []
                )
                self._entity_registry[lookup_key] = new_entity
                self._normalized_index[lookup_key] = resolved_id
                logger.debug(f"[ENTITY_RESOLVER] New entity: {entity_type_upper}:{original_value} -> {resolved_id}")
                return new_entity
    
    def resolve_batch(
        self, 
        entities: List[Dict[str, Any]]
    ) -> List[ResolvedEntity]:
        """
        Resolve a batch of entities efficiently.
        
        Args:
            entities: List of entity dicts with keys: type, value, provenance
            
        Returns:
            List of ResolvedEntity objects
        """
        resolved = []
        for entity in entities:
            entity_type = entity.get("type", "UNKNOWN")
            value = entity.get("value", "")
            provenance = entity.get("provenance", {})
            resolved.append(self.resolve(entity_type, value, provenance))
        return resolved
    
    def get_by_id(self, resolved_id: str) -> Optional[ResolvedEntity]:
        """Get a resolved entity by its ID."""
        with self._lock:
            for entity in self._entity_registry.values():
                if entity.resolved_id == resolved_id:
                    return entity
            return None
    
    def get_all_resolved(self) -> List[ResolvedEntity]:
        """Get all resolved entities."""
        with self._lock:
            return list(self._entity_registry.values())
    
    def clear(self):
        """Clear the registry (useful for testing)."""
        with self._lock:
            self._entity_registry.clear()
            self._normalized_index.clear()
    
    def __len__(self) -> int:
        return len(self._entity_registry)


# Global resolver instance for use across the application
# Can be replaced with request-scoped instances if needed
entity_resolver = EntityResolver()


def resolve_entity(
    entity_type: str, 
    value: str, 
    provenance: Optional[Dict[str, Any]] = None
) -> ResolvedEntity:
    """
    Convenience function to resolve an entity using the global resolver.
    
    Args:
        entity_type: The type of entity
        value: The value of the entity
        provenance: Provenance information
        
    Returns:
        ResolvedEntity with consistent ID
    """
    return entity_resolver.resolve(entity_type, value, provenance)


def resolve_entity_batch(
    entities: List[Dict[str, Any]]
) -> List[ResolvedEntity]:
    """
    Convenience function to resolve a batch of entities.
    
    Args:
        entities: List of entity dicts
        
    Returns:
        List of ResolvedEntity objects
    """
    return entity_resolver.resolve_batch(entities)


def get_entity_registry_stats() -> Dict[str, Any]:
    """Get statistics about the entity registry."""
    with entity_resolver._lock:
        entities = list(entity_resolver._entity_registry.values())
        type_counts = defaultdict(int)
        for entity in entities:
            type_counts[entity.entity_type] += 1
        return {
            "total_entities": len(entities),
            "by_type": dict(type_counts),
            "unique_ids": len(set(e.resolved_id for e in entities))
        }
