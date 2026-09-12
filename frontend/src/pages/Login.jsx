import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield } from 'lucide-react';
import api from '../api/client';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      // Note: this only sends username/password - the backend ignores any
      // client-supplied role and looks up the account's real stored role.
      const res = await api.post('/api/auth/login', { username, password });
      localStorage.setItem('token', res.data.access_token);
      navigate('/');
    } catch (err) {
      if (err.response && err.response.data && err.response.data.detail) {
        // Surfaces real backend messages (locked account + remaining
        // minutes, disabled account, etc.) instead of a single generic line.
        setError(err.response.data.detail);
      } else if (err.request) {
        setError('Could not reach the backend. Is it running?');
      } else {
        setError('Login failed.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-dark-900 px-4 relative overflow-hidden">
      {/* Floating glow particles - CSS-only transform/opacity animation, no
          JS animation loop or canvas, so this costs nothing at runtime. */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-[15%] left-[12%] w-2 h-2 rounded-full bg-cyan-400 shadow-glow-cyan animate-float" style={{ animationDelay: '0s' }} />
        <div className="absolute top-[70%] left-[20%] w-1.5 h-1.5 rounded-full bg-neon-pink shadow-glow-pink animate-float" style={{ animationDelay: '1.2s' }} />
        <div className="absolute top-[25%] right-[15%] w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-primary animate-float" style={{ animationDelay: '2.4s' }} />
        <div className="absolute top-[80%] right-[22%] w-2 h-2 rounded-full bg-cyan-400 shadow-glow-cyan animate-float" style={{ animationDelay: '0.6s' }} />
        <div className="absolute top-[45%] left-[8%] w-1 h-1 rounded-full bg-neon-magenta shadow-glow-pink animate-float" style={{ animationDelay: '3s' }} />
        <div className="absolute top-[10%] right-[35%] w-1 h-1 rounded-full bg-primary-400 shadow-glow-primary animate-float" style={{ animationDelay: '1.8s' }} />
      </div>

      <div className="glass-panel glow-edge p-8 w-full max-w-md relative">
        <div className="flex flex-col items-center mb-8">
          <div className="relative w-20 h-20 flex items-center justify-center mb-4">
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-cyan-400/20 via-primary-500/20 to-neon-pink/20 blur-md" />
            <div className="relative w-16 h-16 bg-dark-900/80 border border-cyan-400/30 rounded-full flex items-center justify-center">
              <Shield className="w-8 h-8 text-cyan-400 animate-pulse-glow" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-white text-glow tracking-wide">NEXUS-X</h1>
          <p className="text-slate-400 mt-2 text-center text-sm">
            Neural Evidence & eXplainable Unified Surveillance Intelligence eXchange
          </p>
        </div>

        {error && <div className="bg-red-500/20 text-red-400 p-3 rounded mb-4 text-sm text-center">{error}</div>}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1">Username</label>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="w-full bg-dark-900 border border-dark-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/40 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1">Password</label>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full bg-dark-900 border border-dark-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400/40 transition-colors"
            />
          </div>
          <button
            type="submit"
            disabled={submitting || !username || !password}
            className="w-full bg-gradient-to-r from-primary-500 to-cyan-500 hover:from-primary-600 hover:to-cyan-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2 rounded-lg transition-all hover:shadow-glow-cyan mt-6"
          >
            {submitting ? 'Authenticating...' : 'Authenticate'}
          </button>
        </form>

        <p className="text-xs text-slate-500 text-center mt-6">
          Accounts are provisioned by an administrator. Contact your system administrator if you need access.
        </p>
      </div>
    </div>
  );
}
