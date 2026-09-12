import { useEffect, useMemo, useState, useCallback } from 'react';
import ReactFlow, {
  ReactFlowProvider, useReactFlow, Background, Controls, MiniMap,
  applyNodeChanges, applyEdgeChanges,
} from 'react-flow-renderer';
import dagre from 'dagre';
import { Search, X } from 'lucide-react';
import api from '../api/client';

const TYPE_COLORS = {
  PERSON: '#3b82f6', PHONE: '#10b981', VEHICLE: '#f59e0b', LOCATION: '#8b5cf6',
  ORGANIZATION: '#ec4899', EVENT: '#64748b', ACCOUNT: '#06b6d4',
};
const NODE_W = 140;
const NODE_H = 46;
// Above this many nodes, dagre's layered layout gets slow enough to notice -
// fall back to a plain grid so the browser doesn't stall on a very large case.
const DAGRE_NODE_LIMIT = 500;

function layoutNodes(nodes, edges) {
  if (nodes.length === 0) return nodes;
  if (nodes.length > DAGRE_NODE_LIMIT) {
    const perRow = Math.ceil(Math.sqrt(nodes.length));
    return nodes.map((n, i) => ({
      ...n,
      position: { x: (i % perRow) * (NODE_W + 40), y: Math.floor(i / perRow) * (NODE_H + 40) },
    }));
  }
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', nodesep: 50, ranksep: 80 });
  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return nodes.map((n) => {
    const pos = g.node(n.id);
    return pos ? { ...n, position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 } } : n;
  });
}

function NetworkExplorerInner() {
  const [rawNodes, setRawNodes] = useState([]);
  const [rawEdges, setRawEdges] = useState([]);
  const [importantById, setImportantById] = useState({});
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const [search, setSearch] = useState('');
  const [hiddenTypes, setHiddenTypes] = useState(() => new Set());
  const [hiddenRelTypes, setHiddenRelTypes] = useState(() => new Set());

  const { setCenter } = useReactFlow();

  const fetchGraph = useCallback(async () => {
    try {
      const [graphRes, importantRes] = await Promise.all([
        api.get('/api/graph'),
        api.get('/api/intelligence/important-nodes').catch(() => ({ data: [] })),
      ]);
      setRawNodes(graphRes.data.nodes || []);
      setRawEdges(graphRes.data.links || []);
      const byId = {};
      for (const n of importantRes.data || []) byId[n.id] = n;
      setImportantById(byId);
      setError(null);
    } catch (e) {
      const detail = e.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to load the knowledge graph. Make sure the backend and Neo4j are running.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchGraph();
    const onIngestionCompleted = () => fetchGraph();
    window.addEventListener('nexus:ingestion-completed', onIngestionCompleted);
    return () => window.removeEventListener('nexus:ingestion-completed', onIngestionCompleted);
  }, [fetchGraph]);

  const entityTypes = useMemo(() => [...new Set(rawNodes.map((n) => n.type))].sort(), [rawNodes]);
  const relTypes = useMemo(() => [...new Set(rawEdges.map((e) => e.type))].sort(), [rawEdges]);

  // Recompute the visible node/edge set (and lay it out) whenever the raw
  // graph or any filter changes - this is what actually implements "filter
  // by entity type", "filter by relationship type" and "search" rather than
  // just decorating the full unfiltered graph.
  useEffect(() => {
    const visibleNodeIds = new Set(
      rawNodes.filter((n) => !hiddenTypes.has(n.type)).map((n) => n.id)
    );
    const visibleEdges = rawEdges.filter(
      (e) => !hiddenRelTypes.has(e.type) && visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
    );

    const searchLower = search.trim().toLowerCase();
    const flowNodes = rawNodes
      .filter((n) => visibleNodeIds.has(n.id))
      .map((n) => {
        const isMatch = searchLower && (
          n.id.toLowerCase().includes(searchLower) || String(n.name).toLowerCase().includes(searchLower)
        );
        return {
          id: n.id,
          data: { label: `${n.name}\n${n.type}` },
          position: { x: 0, y: 0 },
          style: {
            background: TYPE_COLORS[n.type] || '#334155',
            color: '#fff',
            border: isMatch ? '3px solid #fbbf24' : 'none',
            borderRadius: '8px',
            padding: '8px',
            width: NODE_W,
            fontSize: '10px',
            textAlign: 'center',
            whiteSpace: 'pre-line',
            boxShadow: isMatch ? '0 0 12px rgba(251,191,36,0.7)' : 'none',
          },
        };
      });

    const flowEdges = visibleEdges.map((e, i) => ({
      id: e.id || `edge-${i}`,
      source: e.source,
      target: e.target,
      label: e.type,
      animated: true,
      style: { stroke: e.status === 'CONFIRMED' ? '#3B82F6' : '#EF4444' },
    }));

    setNodes(layoutNodes(flowNodes, flowEdges));
    setEdges(flowEdges);
  }, [rawNodes, rawEdges, hiddenTypes, hiddenRelTypes, search]);

  const onNodesChange = (changes) => setNodes((nds) => applyNodeChanges(changes, nds));
  const onEdgesChange = (changes) => setEdges((eds) => applyEdgeChanges(changes, eds));
  const onNodeClick = (_, node) => setSelectedNode(node);

  const toggleType = (type) => {
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      next.has(type) ? next.delete(type) : next.add(type);
      return next;
    });
  };
  const toggleRelType = (type) => {
    setHiddenRelTypes((prev) => {
      const next = new Set(prev);
      next.has(type) ? next.delete(type) : next.add(type);
      return next;
    });
  };

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    const term = search.trim().toLowerCase();
    if (!term) return;
    const match = nodes.find((n) => n.id.toLowerCase().includes(term) || n.data.label.toLowerCase().includes(term));
    if (match) {
      setCenter(match.position.x + NODE_W / 2, match.position.y + NODE_H / 2, { zoom: 1.2, duration: 500 });
    }
  };

  const selectedImportance = selectedNode ? importantById[selectedNode.id] : null;

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      <div className="mb-4 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-white">Network Explorer</h1>
          <p className="text-slate-400">Interactive evidence-backed graph visualization</p>
        </div>
        <form onSubmit={handleSearchSubmit} className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search entity by name or ID..."
              className="bg-dark-900 border border-dark-700 rounded-lg pl-9 pr-8 py-2 text-sm text-white w-64 focus:outline-none focus:border-primary-500"
            />
            {search && (
              <button type="button" onClick={() => setSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </form>
      </div>

      {(entityTypes.length > 0 || relTypes.length > 0) && (
        <div className="mb-4 flex flex-wrap gap-4 text-xs">
          {entityTypes.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-slate-500">Entity types:</span>
              {entityTypes.map((t) => (
                <button
                  key={t}
                  onClick={() => toggleType(t)}
                  className="px-2 py-1 rounded-full border transition-opacity"
                  style={{
                    borderColor: TYPE_COLORS[t] || '#334155',
                    color: hiddenTypes.has(t) ? '#64748b' : (TYPE_COLORS[t] || '#e2e8f0'),
                    opacity: hiddenTypes.has(t) ? 0.4 : 1,
                    background: hiddenTypes.has(t) ? 'transparent' : `${TYPE_COLORS[t] || '#334155'}1a`,
                  }}
                >
                  {t}
                </button>
              ))}
            </div>
          )}
          {relTypes.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-slate-500">Relationships:</span>
              {relTypes.map((t) => (
                <button
                  key={t}
                  onClick={() => toggleRelType(t)}
                  className={`px-2 py-1 rounded-full border transition-opacity ${
                    hiddenRelTypes.has(t) ? 'border-dark-700 text-slate-500 opacity-40' : 'border-primary-500/40 text-primary-400 bg-primary-500/10'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="mb-4 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-sm text-red-400">
          {error}
        </div>
      )}

      <div className="flex-1 flex gap-4">
        <div className="flex-1 glass-panel overflow-hidden relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center text-slate-400 text-sm z-10 pointer-events-none">
              Loading graph...
            </div>
          )}
          {!loading && !error && rawNodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center text-slate-400 text-sm z-10 pointer-events-none">
              No graph data yet. Upload a file in Data Ingestion and wait for it to complete.
            </div>
          )}
          {!loading && !error && rawNodes.length > 0 && nodes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center text-slate-400 text-sm z-10 pointer-events-none">
              No entities match the current filters.
            </div>
          )}
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            fitView
          >
            <Background color="#1e293b" gap={16} />
            <Controls className="bg-dark-800 text-white border-dark-700" />
            <MiniMap
              nodeColor={(n) => n.style?.background || '#334155'}
              maskColor="rgba(15,23,42,0.7)"
              style={{ background: '#0f172a' }}
            />
          </ReactFlow>
        </div>

        {selectedNode && (
          <div className="w-80 glass-panel p-6 overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-white">Node Details</h3>
              <button onClick={() => setSelectedNode(null)} className="text-slate-500 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-slate-500 block mb-1">ID</label>
                <div className="text-sm text-slate-200 break-all">{selectedNode.id}</div>
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">Type</label>
                <div className="text-sm font-medium px-2 py-1 bg-dark-900 rounded inline-block text-primary-400">
                  {selectedNode.data.label.split('\n')[1]}
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">Connected entities</label>
                <div className="text-sm text-slate-200">
                  {edges.filter((e) => e.source === selectedNode.id || e.target === selectedNode.id).length} direct connection(s)
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">Role hypothesis</label>
                <div className="text-sm text-slate-200">
                  {/* Derived from IntelligenceService's real degree/betweenness
                      centrality computation (GET /api/intelligence/important-nodes),
                      not a hardcoded ID check against a fixture that doesn't
                      exist in real case data. */}
                  {selectedImportance
                    ? `${selectedImportance.role} (importance ${selectedImportance.importance_score}/100)`
                    : 'Standard node - not flagged as structurally significant'}
                </div>
              </div>
              <div className="mt-6 pt-4 border-t border-dark-700">
                <p className="text-xs text-slate-500">
                  Structural importance does not imply criminality or guilt.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function NetworkExplorer() {
  return (
    <ReactFlowProvider>
      <NetworkExplorerInner />
    </ReactFlowProvider>
  );
}
