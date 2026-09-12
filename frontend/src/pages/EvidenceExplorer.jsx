import { useEffect, useState } from 'react';
import api from '../api/client';
import { FileKey, ShieldCheck, ShieldAlert, RefreshCw, Link2 } from 'lucide-react';

export default function EvidenceExplorer() {
  const [records, setRecords] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [evidenceId, setEvidenceId] = useState('');
  const [result, setResult] = useState(null);
  const [verifying, setVerifying] = useState(false);
  const [chainResult, setChainResult] = useState(null);
  const [chainVerifying, setChainVerifying] = useState(false);

  const loadRecords = async () => {
    setLoadError(null);
    try {
      const res = await api.get('/api/evidence');
      setRecords(res.data);
      if (!evidenceId && res.data.length > 0) {
        setEvidenceId(res.data[0].id);
      }
    } catch (e) {
      if (e.response && e.response.status === 401) {
        // The shared client's interceptor already redirects to /login on
        // 401 - this only shows if that hasn't kicked in yet.
        setLoadError('Session expired. Please log in again.');
      } else if (e.response) {
        setLoadError(e.response.data?.detail || 'Could not load evidence records.');
      } else {
        setLoadError('Could not reach the backend. Is it running?');
      }
    }
  };

  useEffect(() => {
    loadRecords();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const verifyEvidence = async (id) => {
    const targetId = id || evidenceId;
    if (!targetId) return;
    setEvidenceId(targetId);
    setVerifying(true);
    setResult(null);
    try {
      const res = await api.get(`/api/evidence/${targetId}/verify`);
      setResult(res.data.status);
    } catch (e) {
      setResult('ERROR');
    }
    setVerifying(false);
  };

  const verifyChain = async () => {
    setChainVerifying(true);
    setChainResult(null);
    try {
      const res = await api.get('/api/evidence/chain/verify');
      setChainResult(res.data);
    } catch (e) {
      setChainResult({ status: 'ERROR' });
    }
    setChainVerifying(false);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Evidence Explorer</h1>
        <p className="text-slate-400">Cryptographic tamper-evident ledger verification</p>
      </div>

      <div className="glass-panel p-6">
        <div className="flex items-center justify-between text-primary-400 mb-4">
          <div className="flex items-center">
            <Link2 className="w-5 h-5 mr-2" />
            <h3 className="text-lg font-medium text-white">Evidence Chain</h3>
          </div>
          <button
            onClick={verifyChain}
            disabled={chainVerifying || records.length === 0}
            className="bg-dark-700 hover:bg-dark-600 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {chainVerifying ? 'VERIFYING CHAIN...' : 'VERIFY ENTIRE CHAIN'}
          </button>
        </div>
        <p className="text-xs text-slate-500 mb-4">
          Each evidence record's hash also incorporates the hash of the one before it - like links in a chain.
          Editing, deleting, or reordering any record breaks every hash after it, so the whole case history can be
          proven intact (or not) in one check, not just record-by-record.
        </p>

        {chainResult && (
          <div className={`p-4 rounded-lg border mb-6 text-sm ${chainResult.status === 'VALID' ? 'bg-green-500/10 border-green-500/30 text-green-400' : 'bg-red-500/10 border-red-500/30 text-red-400'}`}>
            {chainResult.status === 'VALID' && (
              <span className="font-bold">CHAIN VALID — {chainResult.length} record{chainResult.length === 1 ? '' : 's'}, unbroken from first to last.</span>
            )}
            {chainResult.status === 'BROKEN' && (
              <div>
                <div className="font-bold mb-1">CHAIN BROKEN at {chainResult.broken_at}</div>
                <div className="text-xs opacity-90">{chainResult.reason}</div>
              </div>
            )}
            {chainResult.status === 'ERROR' && <span className="font-bold">Could not reach server.</span>}
          </div>
        )}

        <div className="border-t border-dark-700 my-6" />

        <div className="flex items-center justify-between text-primary-400 mb-6">
          <div className="flex items-center">
            <FileKey className="w-5 h-5 mr-2" />
            <h3 className="text-lg font-medium text-white">Verify Single Record (SHA-256)</h3>
          </div>
          <button
            onClick={loadRecords}
            className="flex items-center text-xs text-slate-400 hover:text-white transition-colors"
            title="Refresh evidence list"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
          </button>
        </div>

        <div className="flex gap-4 mb-6">
          <input
            type="text"
            value={evidenceId}
            onChange={e => setEvidenceId(e.target.value)}
            placeholder={records.length ? 'Select a record below, or type an ID' : 'Upload a file in Data Ingestion first'}
            className="flex-1 bg-dark-900 border border-dark-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-primary-500 transition-colors"
          />
          <button
            onClick={() => verifyEvidence()}
            disabled={!evidenceId || verifying}
            className="bg-primary-500 hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg font-medium transition-colors"
          >
            {verifying ? 'VERIFYING...' : 'VERIFY INTEGRITY'}
          </button>
        </div>

        {result && (
          <div className={`p-6 rounded-lg border mb-6 ${result === 'VALID' ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
            <div className="flex items-center justify-center mb-4">
              {result === 'VALID' ? (
                <ShieldCheck className="w-12 h-12 text-green-500" />
              ) : (
                <ShieldAlert className="w-12 h-12 text-red-500" />
              )}
            </div>
            <div className={`text-center text-xl font-bold ${result === 'VALID' ? 'text-green-500' : 'text-red-500'}`}>
              {result === 'VALID' ? 'HASH VALID - NO TAMPERING DETECTED' : result === 'ERROR' ? 'COULD NOT REACH SERVER' : 'TAMPER DETECTED - HASH MISMATCH'}
            </div>
            {result === 'VALID' && (
              <p className="text-center text-sm text-slate-400 mt-2">
                The cryptographic hash of the evidence object matches the ledger record.
              </p>
            )}
          </div>
        )}

        <div>
          <h4 className="text-sm font-medium text-slate-300 mb-3">Evidence records ({records.length})</h4>
          {loadError && <p className="text-sm text-red-400">{loadError}</p>}
          {!loadError && records.length === 0 && (
            <p className="text-sm text-slate-500">
              No evidence yet. Upload a file in Data Ingestion and wait for it to reach 100% - each completed
              document gets its own evidence record here automatically.
            </p>
          )}
          <div className="space-y-0">
            {records.map((r, idx) => (
              <div key={r.id}>
                <button
                  onClick={() => verifyEvidence(r.id)}
                  className={`w-full text-left flex items-center justify-between p-3 rounded-lg border transition-colors ${
                    evidenceId === r.id
                      ? 'bg-primary-500/10 border-primary-500/40'
                      : 'bg-dark-900 border-dark-700 hover:bg-dark-800'
                  }`}
                >
                  <div className="min-w-0">
                    <div className="text-sm text-slate-200 font-mono truncate">{r.id}</div>
                    <div className="text-xs text-slate-500 truncate">{r.source}</div>
                  </div>
                  <div className="text-xs text-slate-500 shrink-0 ml-3">
                    {r.timestamp ? new Date(r.timestamp).toLocaleString() : ''}
                  </div>
                </button>
                {idx < records.length - 1 && (
                  <div className="flex items-center justify-center py-1 text-slate-600">
                    <Link2 className="w-3.5 h-3.5" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
