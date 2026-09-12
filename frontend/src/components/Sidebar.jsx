import { Link, useLocation, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Database, Network, Brain, FileKey, Bot, Shield, LogOut } from 'lucide-react';
import clsx from 'clsx';
import api, { getCurrentUser } from '../api/client';

const navItems = [
  { path: '/', label: 'Command Center', icon: LayoutDashboard },
  { path: '/ingest', label: 'Data Ingestion', icon: Database },
  { path: '/network', label: 'Network Explorer', icon: Network },
  { path: '/intelligence', label: 'Intelligence', icon: Brain },
  { path: '/evidence', label: 'Evidence Explorer', icon: FileKey },
  { path: '/copilot', label: 'Investigation Copilot', icon: Bot },
  { path: '/audit', label: 'Audit Logs', icon: Shield, adminOnly: true },
];

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const user = getCurrentUser();

  const handleLogout = async () => {
    try {
      // Best-effort: records the logout in the audit trail. The token is
      // stateless JWT, so this doesn't revoke anything server-side - it's
      // discarded client-side regardless of whether this call succeeds.
      await api.post('/api/auth/logout');
    } catch {
      // Backend unreachable or token already invalid - still proceed to log out locally.
    }
    localStorage.removeItem('token');
    navigate('/login');
  };

  const visibleItems = navItems.filter((item) => !item.adminOnly || user?.role === 'ADMIN');

  return (
    <div className="w-64 bg-dark-800 border-r border-dark-700 flex flex-col min-h-screen">
      <div className="p-6">
        <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-primary-400 to-neon-pink text-glow">
          NEXUS-X
        </h1>
        <p className="text-xs text-slate-400 mt-1">Intelligence Exchange</p>
        {user && (
          <p className="text-xs text-slate-500 mt-2 truncate" title={user.username}>
            {user.username} · <span className="text-primary-400">{user.role}</span>
          </p>
        )}
      </div>

      <nav className="flex-1 px-4 space-y-1 mt-4">
        {visibleItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={clsx(
                'flex items-center px-4 py-3 text-sm rounded-lg transition-all border-l-2',
                isActive
                  ? 'bg-primary-500/10 text-cyan-400 font-medium border-cyan-400 shadow-glow-cyan'
                  : 'text-slate-400 border-transparent hover:bg-dark-700/50 hover:text-slate-200'
              )}
            >
              <Icon className="w-5 h-5 mr-3" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-dark-700">
        <button
          onClick={handleLogout}
          className="flex items-center w-full px-4 py-3 text-sm text-slate-400 rounded-lg hover:bg-dark-700/50 hover:text-red-400 transition-colors"
        >
          <LogOut className="w-5 h-5 mr-3" />
          Logout
        </button>
      </div>
    </div>
  );
}
