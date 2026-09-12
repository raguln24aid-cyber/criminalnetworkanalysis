import { useEffect, useState } from 'react';
import api from '../api/client';
import { Activity, Link2, AlertOctagon, Target } from 'lucide-react';

export default function Intelligence() {
  const [links, setLinks] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [contradictions, setContradictions] = useState([]);
  const [priorities, setPriorities] = useState([]);

  useEffect(() => {
    api.get('/api/intelligence/hidden-links').then(res => setLinks(res.data)).catch(() => {});
    api.get('/api/intelligence/anomalies').then(res => setAnomalies(res.data)).catch(() => {});
    api.get('/api/intelligence/contradictions').then(res => setContradictions(res.data)).catch(() => {});
    api.get('/api/investigation/priorities').then(res => setPriorities(res.data)).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Intelligence Engine</h1>
        <p className="text-slate-400">AI-discovered insights from evidence graph</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Hidden Links */}
        <div className="glass-panel p-6 space-y-4">
          <div className="flex items-center text-primary-400 mb-2">
            <Link2 className="w-5 h-5 mr-2" />
            <h3 className="text-lg font-medium text-white">Potential Hidden Links</h3>
          </div>
          {links.map((link, i) => (
            <div key={i} className="bg-dark-900 border border-dark-700 p-4 rounded-lg">
              <div className="flex justify-between items-center mb-3">
                <span className="font-bold text-slate-200">{link.source} ↔ {link.target}</span>
                <span className="bg-primary-500/10 text-primary-400 px-2 py-1 rounded text-xs font-bold">
                  Score: {link.score}/100
                </span>
              </div>
              <ul className="list-disc list-inside text-xs text-slate-400 space-y-1 mb-3">
                {link.reasons.map((r, idx) => <li key={idx}>{r}</li>)}
              </ul>
              <div className="text-[10px] uppercase font-bold text-yellow-500 bg-yellow-500/10 px-2 py-1 inline-block rounded">
                {link.status}
              </div>
            </div>
          ))}
        </div>

        {/* AI Suggestions (Priorities) */}
        <div className="glass-panel p-6 space-y-4">
          <div className="flex items-center text-green-400 mb-2">
            <Target className="w-5 h-5 mr-2" />
            <h3 className="text-lg font-medium text-white">Investigation Suggestions</h3>
          </div>
          {priorities.map((p, i) => (
            <div key={i} className="bg-dark-900 border border-dark-700 p-4 rounded-lg">
              <div className="flex justify-between items-center mb-3">
                <span className="font-bold text-slate-200">{p.task}</span>
                <span className="bg-green-500/10 text-green-400 px-2 py-1 rounded text-xs font-bold">
                  Score: {p.iig_score}/100
                </span>
              </div>
              <ul className="list-disc list-inside text-xs text-slate-400 space-y-1 mb-3">
                {p.reasons.map((r, idx) => <li key={idx}>{r}</li>)}
              </ul>
              <div className="text-[10px] uppercase font-bold text-green-500 bg-green-500/10 px-2 py-1 inline-block rounded">
                {p.status}
              </div>
            </div>
          ))}
        </div>

        {/* Anomalies */}
        <div className="glass-panel p-6 space-y-4">
          <div className="flex items-center text-amber-400 mb-2">
            <Activity className="w-5 h-5 mr-2" />
            <h3 className="text-lg font-medium text-white">Behavioral Anomalies</h3>
          </div>
          {anomalies.map((anom, i) => (
            <div key={i} className="bg-dark-900 border border-dark-700 p-4 rounded-lg">
              <div className="flex justify-between items-center mb-3">
                <span className="font-bold text-slate-200">{anom.entity_id}</span>
                <span className="bg-amber-500/10 text-amber-400 px-2 py-1 rounded text-xs font-bold">
                  Score: {anom.anomaly_score}/100
                </span>
              </div>
              <p className="text-sm text-slate-300 mb-2">{anom.description}</p>
              <div className="flex gap-4 text-xs text-slate-500">
                <div>Normal: <span className="text-slate-400">{anom.normal_pattern}</span></div>
                <div>Detected: <span className="text-amber-400">{anom.detected_pattern}</span></div>
              </div>
            </div>
          ))}
        </div>

        {/* Contradictions */}
        <div className="glass-panel p-6 space-y-4 lg:col-span-2">
          <div className="flex items-center text-red-400 mb-2">
            <AlertOctagon className="w-5 h-5 mr-2" />
            <h3 className="text-lg font-medium text-white">Evidence Contradictions</h3>
          </div>
          {contradictions.map((contra, i) => (
            <div key={i} className="bg-dark-900 border border-red-500/30 p-4 rounded-lg">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div className="bg-dark-800 p-3 rounded">
                  <div className="text-xs text-slate-500 mb-1">Source A Says</div>
                  <div className="text-sm text-slate-300">{contra.source_a}</div>
                </div>
                <div className="bg-dark-800 p-3 rounded">
                  <div className="text-xs text-slate-500 mb-1">Source B Suggests</div>
                  <div className="text-sm text-slate-300">{contra.source_b}</div>
                </div>
              </div>
              <div className="text-xs text-slate-400 mb-2">Possible explanations:</div>
              <div className="flex flex-wrap gap-2 mb-3">
                {contra.explanations.map((exp, idx) => (
                  <span key={idx} className="bg-dark-800 border border-dark-700 px-2 py-1 rounded text-xs text-slate-300">
                    {exp}
                  </span>
                ))}
              </div>
              <div className="text-[10px] uppercase font-bold text-red-400 bg-red-500/10 px-2 py-1 inline-block rounded">
                {contra.status}
              </div>
            </div>
          ))}
        </div>

      </div>
    </div>
  );
}
