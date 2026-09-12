import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Login from './pages/Login';
import CommandCenter from './pages/CommandCenter';
import DataIngestion from './pages/DataIngestion';
import NetworkExplorer from './pages/NetworkExplorer';
import Intelligence from './pages/Intelligence';
import EvidenceExplorer from './pages/EvidenceExplorer';
import Copilot from './pages/Copilot';
import AuditLogs from './pages/AuditLogs';
import { isTokenValid, getCurrentUser } from './api/client';

function App() {
  // Checks the token's own exp claim, not just "some string is present" -
  // an expired token left in localStorage used to still count as "logged
  // in" client-side right up until the first API call came back 401.
  const isAuthenticated = isTokenValid(localStorage.getItem('token'));
  const user = isAuthenticated ? getCurrentUser() : null;

  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />

        {/* Protected Routes */}
        <Route path="/" element={isAuthenticated ? <Layout /> : <Navigate to="/login" />}>
          <Route index element={<CommandCenter />} />
          <Route path="ingest" element={<DataIngestion />} />
          <Route path="network" element={<NetworkExplorer />} />
          <Route path="intelligence" element={<Intelligence />} />
          <Route path="evidence" element={<EvidenceExplorer />} />
          <Route path="copilot" element={<Copilot />} />
          <Route
            path="audit"
            element={user?.role === 'ADMIN' ? <AuditLogs /> : <Navigate to="/" />}
          />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
