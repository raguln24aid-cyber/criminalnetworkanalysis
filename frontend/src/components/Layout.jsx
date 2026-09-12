import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-dark-900">
      <Sidebar />
      <main className="flex-1 p-8 overflow-y-auto">
        <div className="mb-4 text-xs text-slate-500 bg-dark-800 p-2 rounded flex justify-center items-center">
          <span className="bg-yellow-500/20 text-yellow-500 px-2 py-1 rounded mr-2">NOTICE</span>
          AI-generated relationships are investigative leads, not proof of criminal activity. Final decisions require authorized human investigation and verification.
        </div>
        <Outlet />
      </main>
    </div>
  );
}
