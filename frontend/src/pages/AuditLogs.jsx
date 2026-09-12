import { useEffect, useState } from 'react';
import api from '../api/client';
import { Shield } from 'lucide-react';

export default function AuditLogs() {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ user: '', action: '', resource_type: '' });

  const load = () => {
    setLoading(true);
    setError(null);
    const params = {};
    if (filters.user) params.user = filters.user;
    if (filters.action) params.action = filters.action;
    if (filters.resource_type) params.resource_type = filters.resource_type;

    api.get('/api/audit', { params })
      .then(res => {
        setLogs(res.data.results || []);
        setTotal(res.data.total || 0);
      })
      .catch(err => {
        if (err.response?.status === 403) {
          setError('Audit logs are restricted to administrators.');
        } else {
          setError('Could not load audit logs.');
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFilterSubmit = (e) => {
    e.preventDefault();
    load();
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Audit Logs</h1>
        <p className="text-slate-400">System access and action records (admin only)</p>
      </div>

      <form onSubmit={handleFilterSubmit} className="glass-panel p-4 flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-slate-500 mb-1">User</label>
          <input
            value={filters.user}
            onChange={e => setFilters(f => ({ ...f, user: e.target.value }))}
            className="bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-primary-500"
            placeholder="username"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Action</label>
          <input
            value={filters.action}
            onChange={e => setFilters(f => ({ ...f, action: e.target.value }))}
            className="bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-primary-500"
            placeholder="e.g. LOGIN, UPLOAD"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Resource type</label>
          <input
            value={filters.resource_type}
            onChange={e => setFilters(f => ({ ...f, resource_type: e.target.value }))}
            className="bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-primary-500"
            placeholder="e.g. document, evidence"
          />
        </div>
        <button type="submit" className="bg-primary-500 hover:bg-primary-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
          Filter
        </button>
        {total > 0 && <span className="text-xs text-slate-500 ml-auto">{total} total record{total === 1 ? '' : 's'}</span>}
      </form>

      <div className="glass-panel overflow-hidden">
        <div className="p-4 border-b border-dark-700 flex items-center bg-dark-800/50">
          <Shield className="w-5 h-5 text-primary-400 mr-2" />
          <h3 className="font-medium text-white">Security & Action Ledger</h3>
        </div>

        {error && <div className="p-6 text-center text-sm text-red-400">{error}</div>}

        {!error && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-dark-900/50 text-slate-400">
                <tr>
                  <th className="px-6 py-3 font-medium">Timestamp</th>
                  <th className="px-6 py-3 font-medium">User</th>
                  <th className="px-6 py-3 font-medium">Action</th>
                  <th className="px-6 py-3 font-medium">Resource</th>
                  <th className="px-6 py-3 font-medium">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-700">
                {logs.length > 0 ? logs.map((log) => (
                  <tr key={log.id} className="hover:bg-dark-800/50 transition-colors">
                    <td className="px-6 py-4 text-slate-300">{new Date(log.timestamp).toLocaleString()}</td>
                    <td className="px-6 py-4 text-slate-300">{log.user}</td>
                    <td className="px-6 py-4 text-slate-300">{log.action}</td>
                    <td className="px-6 py-4 text-slate-300">
                      {log.resource_type}{log.resource_id ? ` (${log.resource_id})` : ''}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        log.result === 'SUCCESS' ? 'bg-green-500/10 text-green-400' : 'bg-amber-500/10 text-amber-400'
                      }`}>
                        {log.result}
                      </span>
                    </td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan="5" className="px-6 py-8 text-center text-slate-500">
                      {loading ? 'Loading...' : 'No audit log entries match this filter.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
