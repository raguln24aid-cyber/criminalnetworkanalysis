"""
Intelligence Engine for NEXUS-X.

Previously every method here returned hardcoded demo data (fake entity IDs
like "P001"/"P009"/"Account A007" that don't exist in any real case), and
get_important_nodes() lived in GraphService reading from SQL Entity/
Relationship tables the ingestion pipeline never writes to - so every
"insight" was either fabricated or silently empty.

This version builds an in-memory NetworkX graph from the real Neo4j case
graph (the same store Network Explorer and the Copilot read from) and runs
actual graph algorithms against it:
  - hidden links: link prediction via common-neighbor / Adamic-Adar scoring
    on entity pairs that aren't already directly connected
  - anomalies: degree z-score outliers (entities with far more connections
    than the network average)
  - contradictions: entities linked to more than one distinct location,
    flagged for human verification (not asserted as fact)
  - important nodes / investigation priorities: degree + betweenness
    centrality, folded together with the findings above

All of it is computed from whatever is actually in the graph - with no
documents ingested it correctly returns empty lists, not canned examples.
"""

import logging
import statistics
from collections import defaultdict
from typing import Any, Dict, List

import networkx as nx
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

LOCATION_REL_TYPES = {"LOCATED_AT", "OBSERVED_AT"}


class IntelligenceService:
    def __init__(self, db: Session = None):
        self.db = db
        self.G = nx.Graph()
        self.DG = nx.DiGraph()
        self._load_graph()

    def _load_graph(self):
        from app.neo4j_db import neo4j_service

        if neo4j_service.driver is None:
            return

        node_results = neo4j_service.execute_read("MATCH (n) RETURN n") or []
        for res in node_results:
            n = res.get("n")
            if not n or n.get("id") is None:
                continue
            node_id = n["id"]
            attrs = {"type": n.get("type", "UNKNOWN"), "value": n.get("value", node_id)}
            self.G.add_node(node_id, **attrs)
            self.DG.add_node(node_id, **attrs)

        edge_results = neo4j_service.execute_read("""
            MATCH (a)-[r]->(b)
            RETURN a.id AS source, b.id AS target, type(r) AS rel_type,
                   r.evidence_doc AS doc, r.evidence_row AS row, r.status AS status
        """) or []
        for e in edge_results:
            src, tgt = e.get("source"), e.get("target")
            if src is None or tgt is None or src not in self.G or tgt not in self.G:
                continue
            attrs = {"type": e.get("rel_type"), "doc": e.get("doc"), "row": e.get("row"), "status": e.get("status")}
            self.G.add_edge(src, tgt, **attrs)
            self.DG.add_edge(src, tgt, **attrs)

    def _label(self, node_id: str) -> str:
        node = self.G.nodes.get(node_id, {})
        return node.get("value", node_id)

    def get_hidden_links(self, top_k: int = 5) -> List[Dict[str, Any]]:
        """Link prediction: entity pairs with no direct edge but several
        shared neighbors, scored via Adamic-Adar (weights rarer/more
        specific shared connections higher than common ones)."""
        if self.G.number_of_nodes() < 3:
            return []

        results = []
        nodes = list(self.G.nodes())
        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                if self.G.has_edge(a, b):
                    continue
                common = list(nx.common_neighbors(self.G, a, b))
                if len(common) < 2:
                    continue
                try:
                    aa_score = next(iter(nx.adamic_adar_index(self.G, [(a, b)])))[2]
                except (StopIteration, ZeroDivisionError):
                    aa_score = 0.0
                score = min(99, round(aa_score * 25 + len(common) * 8))
                if score <= 0:
                    continue
                reasons = [
                    f"Shared connection: {self._label(c)} ({self.G.nodes[c].get('type', 'ENTITY')})"
                    for c in common[:5]
                ]
                results.append({
                    "source": self._label(a),
                    "target": self._label(b),
                    "score": score,
                    "reasons": reasons,
                    "status": "POTENTIAL LEAD — REQUIRES VERIFICATION",
                })

        results.sort(key=lambda x: -x["score"])
        return results[:top_k]

    def get_anomalies(self, z_threshold: float = 1.5, min_degree: int = 3) -> List[Dict[str, Any]]:
        """Flags entities whose connection count is a statistical outlier
        (z-score) against the rest of the network - a real signal that an
        entity is unusually central to the case, computed from actual
        degree, not a scripted example."""
        if self.G.number_of_nodes() < 3:
            return []

        degrees = dict(self.G.degree())
        values = list(degrees.values())
        mean = statistics.mean(values)
        stdev = statistics.pstdev(values) if len(values) > 1 else 0

        anomalies = []
        if stdev > 0:
            for node_id, deg in degrees.items():
                z = (deg - mean) / stdev
                if z >= z_threshold and deg >= min_degree:
                    node = self.G.nodes[node_id]
                    anomalies.append({
                        "entity_id": node.get("value", node_id),
                        "description": (
                            f"{node.get('type', 'Entity')} \"{node.get('value', node_id)}\" has {deg} "
                            f"connections in the case graph - well above the network average."
                        ),
                        "normal_pattern": f"~{mean:.1f} connections (network average)",
                        "detected_pattern": f"{deg} connections (z-score {z:.1f})",
                        "anomaly_score": min(99, round(50 + z * 15)),
                    })

        anomalies.sort(key=lambda x: -x["anomaly_score"])
        return anomalies[:10]

    def get_contradictions(self) -> List[Dict[str, Any]]:
        """Flags entities linked to more than one distinct location across
        the evidence. This is surfaced as something requiring verification,
        not asserted as a confirmed contradiction - the graph doesn't carry
        enough timestamp precision on these edges to prove overlap on its
        own."""
        entity_locations = defaultdict(list)
        for u, v, data in self.DG.edges(data=True):
            if data.get("type") not in LOCATION_REL_TYPES:
                continue
            v_node = self.DG.nodes.get(v, {})
            if v_node.get("type") != "LOCATION":
                continue
            entity_locations[u].append((self._label(v), data.get("doc"), data.get("row")))

        contradictions = []
        for entity_id, locs in entity_locations.items():
            distinct = {}
            for val, doc, row in locs:
                distinct.setdefault(val, (doc, row))
            if len(distinct) < 2:
                continue
            entity_node = self.DG.nodes.get(entity_id, {})
            loc_items = list(distinct.items())
            (loc_a, (doc_a, row_a)), (loc_b, (doc_b, row_b)) = loc_items[0], loc_items[1]
            contradictions.append({
                "entities": [entity_node.get("value", entity_id), loc_a, loc_b],
                "source_a": f"{entity_node.get('type', 'Entity')} \"{entity_node.get('value', entity_id)}\" is linked to \"{loc_a}\" (evidence: {doc_a}#row{row_a}).",
                "source_b": f"The same entity is also linked to \"{loc_b}\" (evidence: {doc_b}#row{row_b}).",
                "explanations": [
                    "Multiple sightings over time (not necessarily contradictory)",
                    "Data entry or extraction error",
                    "Shared device or identity",
                    "Requires timestamp correlation to confirm a true conflict",
                ],
                "status": "REQUIRES HUMAN VERIFICATION",
            })

        return contradictions[:10]

    def get_important_nodes(self) -> List[Dict[str, Any]]:
        """Degree + betweenness centrality on the real case graph - flags
        hubs (high degree) and bridges (high betweenness) worth prioritizing."""
        if self.G.number_of_nodes() == 0:
            return []

        degree_cent = nx.degree_centrality(self.G)
        try:
            betweenness_cent = nx.betweenness_centrality(self.G)
        except Exception:
            betweenness_cent = {n: 0 for n in self.G.nodes()}

        important = []
        for n in self.G.nodes():
            dc = degree_cent.get(n, 0)
            bc = betweenness_cent.get(n, 0)
            score = (dc + bc) / 2
            if score > 0.1:
                important.append({
                    "id": n,
                    "name": self.G.nodes[n].get("value", ""),
                    "type": self.G.nodes[n].get("type", ""),
                    "importance_score": round(score * 100, 2),
                    "role": "Potential Bridge" if bc > dc else "Operational Node",
                })
        return sorted(important, key=lambda x: x["importance_score"], reverse=True)[:10]

    def get_investigation_priorities(self, top_k: int = 5) -> List[Dict[str, Any]]:
        """Combines hidden links, degree/betweenness centrality and anomaly
        flags into a ranked worklist - every task references a real entity
        or pair from the actual case graph."""
        if self.G.number_of_nodes() < 2:
            return []

        degree_cent = nx.degree_centrality(self.G)
        try:
            betweenness_cent = nx.betweenness_centrality(self.G)
        except Exception:
            betweenness_cent = {n: 0 for n in self.G.nodes()}

        anomaly_ids = {a["entity_id"] for a in self.get_anomalies()}
        tasks = []

        for link in self.get_hidden_links(top_k=5):
            tasks.append({
                "task": f"Verify potential link between {link['source']} and {link['target']}",
                "iig_score": link["score"],
                "reasons": link["reasons"] + ["High information gain if confirmed or ruled out"],
                "status": "Pending",
            })

        for node_id, dc in sorted(degree_cent.items(), key=lambda x: -x[1])[:top_k]:
            node = self.G.nodes[node_id]
            value = node.get("value", node_id)
            bc = betweenness_cent.get(node_id, 0)
            reasons = [f"High network centrality ({dc * 100:.0f}%)"]
            if bc > 0.05:
                reasons.append(f"Structural bridge between clusters (betweenness {bc * 100:.0f}%)")
            if value in anomaly_ids:
                reasons.append("Flagged as a behavioral anomaly")
            tasks.append({
                "task": f"Investigate {node.get('type', 'entity').lower()} \"{value}\" further",
                "iig_score": min(99, round((dc + bc) * 100)),
                "reasons": reasons,
                "status": "Pending",
            })

        seen = set()
        deduped = []
        for t in sorted(tasks, key=lambda x: -x["iig_score"]):
            if t["task"] in seen:
                continue
            seen.add(t["task"])
            deduped.append(t)
        return deduped[:top_k]
