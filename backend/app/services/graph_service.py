import networkx as nx
from sqlalchemy.orm import Session
from app.models.domain import Entity, Relationship

class GraphService:
    def __init__(self, db: Session):
        self.db = db
        self.G = nx.Graph()
        self._build_graph()

    def _build_graph(self):
        entities = self.db.query(Entity).all()
        relationships = self.db.query(Relationship).all()
        
        for e in entities:
            self.G.add_node(e.id, type=e.type, name=e.name)
            
        for r in relationships:
            self.G.add_edge(r.source_id, r.target_id, 
                            id=r.id, type=r.type, 
                            timestamp=r.timestamp, 
                            confidence=r.confidence,
                            status=r.status)

    def get_graph_data(self):
        import json
        nodes = [{"id": n, **d} for n, d in self.G.nodes(data=True)]
        edges = [{"source": u, "target": v, **d} for u, v, d in self.G.edges(data=True)]
        return {"nodes": nodes, "links": edges}

    def get_network_stats(self):
        return {
            "num_nodes": self.G.number_of_nodes(),
            "num_edges": self.G.number_of_edges(),
            "density": nx.density(self.G) if self.G.number_of_nodes() > 0 else 0
        }

    def get_important_nodes(self):
        if self.G.number_of_nodes() == 0:
            return []
        
        degree_cent = nx.degree_centrality(self.G)
        betweenness_cent = nx.betweenness_centrality(self.G)
        
        important = []
        for n in self.G.nodes():
            dc = degree_cent.get(n, 0)
            bc = betweenness_cent.get(n, 0)
            score = (dc + bc) / 2
            if score > 0.1: # Threshold
                important.append({
                    "id": n,
                    "name": self.G.nodes[n].get("name", ""),
                    "type": self.G.nodes[n].get("type", ""),
                    "importance_score": round(score * 100, 2),
                    "role": "Potential Bridge" if bc > dc else "Operational Node"
                })
        return sorted(important, key=lambda x: x["importance_score"], reverse=True)[:10]

    def remove_node_simulate(self, node_id: str):
        if node_id not in self.G:
            return None
        
        initial_components = nx.number_connected_components(self.G)
        
        # Create a copy and remove node
        H = self.G.copy()
        H.remove_node(node_id)
        
        new_components = nx.number_connected_components(H)
        
        return {
            "node_id": node_id,
            "initial_components": initial_components,
            "new_components": new_components,
            "fragmentation_increase": new_components - initial_components
        }
