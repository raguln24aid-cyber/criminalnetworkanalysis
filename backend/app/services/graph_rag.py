"""
Graph RAG retrieval for the Investigation Copilot.

Previously _build_case_context() (endpoints.py) just dumped the first ~100
entities and ~100 relationships from Neo4j into the prompt every time,
regardless of what was actually asked, then hard-truncated the whole thing
at a fixed character budget. Neo4j returns rows in no particular order (no
ORDER BY), so whether a given entity's facts survived into what the LLM
actually saw was pure luck - an entity mentioned in the question could be
sitting in the graph with real relationships and still get cut, simply
because the truncation point landed before its rows.

This module makes retrieval query-aware: it pulls out the likely entity
names/keywords in the investigator's question, searches the graph for
matching nodes, and retrieves their FULL neighborhood (not capped, since a
single entity's connections are a small, bounded set even in a large case
graph). That subgraph is guaranteed to survive into the prompt ahead of the
general overview - real retrieval-augmented generation over the graph,
instead of "hope it fits."
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import re

logger = logging.getLogger(__name__)

# Generic words stripped out before searching for entity names in a
# question - deliberately broad rather than a real NLP NER model, but
# effective for the "explain X" / "who is X" / "how is X connected to Y"
# style questions investigators actually type.
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "of", "in", "on",
    "at", "to", "for", "with", "and", "or", "who", "what", "when", "where", "why",
    "how", "which", "this", "that", "these", "those", "explain", "details", "detail",
    "tell", "me", "about", "give", "show", "find", "please", "list", "summarize",
    "summary", "describe", "information", "info", "case", "data", "entity",
    "entities", "relationship", "relationships", "graph", "between", "connect",
    "connected", "connection", "connections", "link", "links", "linked", "all",
    "any", "does", "do", "did", "can", "could", "would", "should", "there",
    "exist", "exists", "have", "has", "had", "know", "known", "investigate",
    "investigation", "query", "question", "answer", "you", "your", "i", "my",
}


def extract_search_terms(query: str) -> List[str]:
    """Turns a natural-language question into an ordered list of candidate
    graph-search terms: the full remaining phrase first (best for multi-word
    names like "arjun mehta"), then each individual word as a fallback."""
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]*", query.lower())
    meaningful = [w for w in words if w not in STOPWORDS and len(w) > 1]
    if not meaningful:
        return []
    terms = [" ".join(meaningful)] + meaningful
    seen, ordered = set(), []
    for t in terms:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered


def _find_matching_entities(neo4j_service, terms: List[str], limit: int = 15) -> List[Dict[str, Any]]:
    """Tries each search term in order (full phrase, then individual words)
    and stops at the first term that actually matches something - so asking
    about "arjun mehta" doesn't fall back to a flood of unrelated single-word
    "arjun" or "mehta" matches when the full-name match already succeeded."""
    for term in terms:
        results = neo4j_service.execute_read(
            "MATCH (n) WHERE toLower(n.value) CONTAINS $term RETURN DISTINCT n LIMIT $limit",
            {"term": term, "limit": limit},
        ) or []
        matches = [r["n"] for r in results if r.get("n") and r["n"].get("id")]
        if matches:
            return matches
    return []


def _neighborhood_for(neo4j_service, entity_ids: List[str]) -> List[Dict[str, Any]]:
    """Full 1-hop neighborhood of the matched entities, both directions -
    not capped, because one entity's real-world connection count is small
    even in a large case graph, unlike the whole graph's edge count."""
    if not entity_ids:
        return []
    return neo4j_service.execute_read(
        """
        MATCH (n)-[r]-(m)
        WHERE n.id IN $ids
        RETURN DISTINCT n.id AS n_id,
               startNode(r).id AS src_id, startNode(r).type AS src_type, startNode(r).value AS src_value,
               type(r) AS rel_type,
               endNode(r).id AS tgt_id, endNode(r).type AS tgt_type, endNode(r).value AS tgt_value,
               r.evidence_doc AS doc, r.evidence_row AS row, r.status AS status
        """,
        {"ids": entity_ids},
    ) or []


def retrieve_relevant_subgraph(query: str, max_entities: int = 15) -> Tuple[Optional[str], List[str]]:
    """Query-aware graph retrieval for the Copilot. Returns (context_text,
    evidence_sources) - context_text is None if the question didn't name
    anything findable in the graph, so the caller can fall back to a general
    overview instead of claiming a targeted search came up empty."""
    from app.neo4j_db import neo4j_service

    if neo4j_service.driver is None:
        return None, []

    terms = extract_search_terms(query)
    if not terms:
        return None, []

    matched = _find_matching_entities(neo4j_service, terms, limit=max_entities)
    if not matched:
        return None, []

    matched_ids = [m["id"] for m in matched]
    edges = _neighborhood_for(neo4j_service, matched_ids)

    lines = [f"- {m.get('type', 'UNKNOWN')} \"{m.get('value', m['id'])}\" (id={m['id']})" for m in matched]
    entity_block = "MATCHED ENTITIES (directly retrieved for this question):\n" + "\n".join(lines)

    evidence_sources: List[str] = []
    rel_lines = []
    seen_edges = set()
    for e in edges:
        key = (e.get("src_id"), e.get("rel_type"), e.get("tgt_id"), e.get("row"))
        if key in seen_edges:
            continue
        seen_edges.add(key)
        doc = e.get("doc")
        if doc:
            evidence_sources.append(doc)
        rel_lines.append(
            f"- {e.get('src_type')} \"{e.get('src_value')}\" -[{e.get('rel_type')}]-> "
            f"{e.get('tgt_type')} \"{e.get('tgt_value')}\" "
            f"(status={e.get('status')}, evidence={doc}#row{e.get('row')})"
        )

    sections = [entity_block]
    if rel_lines:
        sections.append(
            "DIRECT CONNECTIONS OF THE MATCHED ENTITIES (complete, not sampled):\n" + "\n".join(rel_lines)
        )
    else:
        sections.append("DIRECT CONNECTIONS OF THE MATCHED ENTITIES: none recorded in the graph.")

    logger.info(f"[GRAPH_RAG] Query {query!r} matched {len(matched)} entities, {len(rel_lines)} relationships")
    return "\n\n".join(sections), sorted(set(evidence_sources))
