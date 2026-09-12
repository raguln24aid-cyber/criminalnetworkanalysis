import { useState, useEffect } from 'react';
import api from '../api/client';
import { Users, AlertTriangle, Link as LinkIcon, Activity } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const TYPE_COLORS = {
  PERSON: '#3b82f6', PHONE: '#10b981', VEHICLE: '#f59e0b', LOCATION: '#8b5cf6',
  ORGANIZATION: '#ec4899', EVENT: '#64748b', ACCOUNT: '#06b6d4',
};

export default function CommandCenter() {
  const [stats, setStats] = useState({ nodes: 0, edges: 0, hiddenLinks: 0, anomalies: 0 });
  const [typeBreakdown, setTypeBreakdown] = useState([]);
  const [priorities, setPriorities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [graphRes, prioRes, linksRes, anomRes] = await Promise.all([
          api.get('/api/graph'),
          api.get('/api/investigation/priorities'),
          api.get('/api/intelligence/hidden-links'),
          api.get('/api/intelligence/anomalies'),
        ]);

        const nodes = graphRes.data.nodes || [];
        const counts = {};
        for (const n of nodes) {
          counts[n.type] = (counts[n.type] || 0) + 1;
        }
        setTypeBreakdown(
          Object.entries(counts)
            .sort((a, b) => b[1] - a[1])
            .map(([type, count]) => ({ name: type, count }))
        );

        setStats({
          nodes: nodes.length,
          edges: (graphRes.data.links || []).length,
          hiddenLinks: (linksRes.data || []).length,
          anomalies: (anomRes.data || []).length,
        });
        setPriorities(prioRes.data || []);
        setError(null);
      } catch (e) {
        setError('Could not load case statistics. Is the backend running?');
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  // Every number here comes from the real graph/intelligence endpoints -
  // no placeholder fallback values (this used to show "50" / "500+" / "1"
  // whenever the real counts were falsy, including when they were 0).
  const statCards = [
    { title: 'Total Entities', value: stats.nodes, icon: Users, color: 'text-blue-400' },
    { title: 'Total Relationships', value: stats.edges, icon: LinkIcon, color: 'text-indigo-400' },
    { title: 'Potential Hidden Links', value: stats.hiddenLinks, icon: Activity, color: 'text-purple-400' },
    { title: 'Anomalies Detected', value: stats.anomalies, icon: AlertTriangle, color: 'text-amber-400' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Command Center</h1>
        <p className="text-slate-400">System overview and investigation priorities</p>
      </div>

      {error && (
        <div className="px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-sm text-red-400">{error}</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((s, i) => {
          const Icon = s.icon;
          return (
            <div key={i} className="glass-panel p-6">
              <div className="flex items-center justify-between mb-4">
                <div className={`p-3 rounded-lg bg-dark-900 ${s.color}`}>
                  <Icon className="w-6 h-6" />
                </div>
              </div>
              <h3 className="text-3xl font-bold text-white">{loading ? '—' : s.value}</h3>
              <p className="text-sm text-slate-400 mt-1">{s.title}</p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 glass-panel p-6">
          <h3 className="text-lg font-medium text-white mb-6">Entity Type Breakdown</h3>
          <div className="h-64">
            {typeBreakdown.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={typeBreakdown}>
                  <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#64748b" allowDecimals={false} />
                  <Tooltip cursor={{ fill: '#1e293b' }} contentStyle={{ backgroundColor: '#0f172a', border: 'none', borderRadius: '8px' }} />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {typeBreakdown.map((entry, i) => (
                      <Cell key={entry.name} fill={TYPE_COLORS[entry.name] || '#3b82f6'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-sm text-slate-500">
                {loading ? 'Loading...' : 'No entities yet - upload a file in Data Ingestion.'}
              </div>
            )}
          </div>
        </div>

        <div className="glass-panel p-6">
          <h3 className="text-lg font-medium text-white mb-4">Top Investigation Priorities</h3>
          <div className="space-y-4">
            {priorities.map((p, i) => (
              <div key={i} className="p-4 rounded-lg bg-dark-900 border border-dark-700">
                <div className="flex justify-between items-start mb-2">
                  <span className="text-sm font-medium text-slate-200">{p.task}</span>
                  <span className="text-xs font-bold text-primary-400 bg-primary-500/10 px-2 py-1 rounded">IIG: {p.iig_score}</span>
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {p.reasons.slice(0, 2).map((r, idx) => (
                    <span key={idx} className="text-[10px] bg-dark-800 text-slate-400 px-2 py-1 rounded">{r}</span>
                  ))}
                </div>
              </div>
            ))}
            {priorities.length === 0 && (
              <div className="text-slate-400 text-sm text-center py-4">
                {loading ? 'Loading...' : 'No priorities generated yet.'}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
