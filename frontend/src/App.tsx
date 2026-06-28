import React, { useState, useEffect } from 'react';
import api from './services/api';
import wsService from './services/websocket';
import CommandCenter from './pages/CommandCenter';
import AgentStudio from './pages/AgentStudio';
import WorkflowStudio from './pages/WorkflowStudio';
import Login from './pages/Login';

type Page = 'command-center' | 'agent-studio' | 'workflow-studio' | 'marketplace' | 'billing';

const NAV_ITEMS: { id: Page; label: string; icon: string }[] = [
  { id: 'command-center', label: 'Command Center', icon: '◉' },
  { id: 'agent-studio', label: 'Agent Studio', icon: '◆' },
  { id: 'workflow-studio', label: 'Workflow Studio', icon: '◇' },
  { id: 'marketplace', label: 'Marketplace', icon: '▣' },
  { id: 'billing', label: 'Billing', icon: '◎' },
];

export default function App() {
  const [page, setPage] = useState<Page>('command-center');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [token, setToken] = useState<string | null>(localStorage.getItem('auth_token'));

  useEffect(() => {
    if (token) {
      wsService.connect('/ws/command-center', '');
      setIsLoggedIn(true);
      api.getMe().then(u => setUser(u)).catch(() => {});
    }
    const unsub = wsService.on('connection', (d) => setWsConnected(d.status === 'connected'));
    return unsub;
  }, [token]);

  const handleLogin = (token: string, user: any) => {
    api.setToken(token);
    setToken(token);
    setUser(user);
    setIsLoggedIn(true);
    wsService.connect('/ws/command-center', user.tenant_id || '');
  };

  const handleLogout = () => {
    api.setToken(null);
    setToken(null);
    setUser(null);
    setIsLoggedIn(false);
    wsService.disconnect();
  };

  if (!isLoggedIn) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside style={{
        width: 240, background: 'var(--bg-secondary)', borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', flexShrink: 0,
      }}>
        <div style={{ padding: '20px 16px', borderBottom: '1px solid var(--border)' }}>
          <h1 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent)' }}>
            Agent OS V6.0
          </h1>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>
            AI Agent Operating System
          </div>
        </div>

        <nav style={{ flex: 1, padding: '12px 8px' }}>
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              onClick={() => setPage(item.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                width: '100%', padding: '10px 12px', borderRadius: 'var(--radius)',
                marginBottom: 4, fontSize: '0.9rem',
                background: page === item.id ? 'var(--bg-hover)' : 'transparent',
                color: page === item.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                border: 'none', cursor: 'pointer', textAlign: 'left',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => { if (page !== item.id) e.currentTarget.style.background = 'var(--bg-hover)'; }}
              onMouseLeave={e => { if (page !== item.id) e.currentTarget.style.background = 'transparent'; }}
            >
              <span style={{ fontSize: '1.1rem' }}>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        <div style={{ padding: '16px', borderTop: '1px solid var(--border)' }}>
          <div style={{ fontSize: '0.85rem', marginBottom: 8 }}>
            {user?.username || user?.email || 'User'}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: wsConnected ? 'var(--success)' : 'var(--danger)',
            }} />
            <span className="text-sm text-muted">{wsConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
          <button onClick={handleLogout} className="btn btn-secondary btn-sm w-full">
            Logout
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
        {page === 'command-center' && <CommandCenter user={user} />}
        {page === 'agent-studio' && <AgentStudio user={user} />}
        {page === 'workflow-studio' && <WorkflowStudio user={user} />}
        {page === 'marketplace' && <Marketplace user={user} />}
        {page === 'billing' && <Billing user={user} />}
      </main>
    </div>
  );
}

function Marketplace({ user }: { user: any }) {
  const [agents, setAgents] = useState<any[]>([]);
  useEffect(() => { api.getMarketplaceList().then(setAgents).catch(() => {}); }, []);
  return (
    <div>
      <h2 style={{ fontSize: '1.5rem', marginBottom: 20 }}>Agent Marketplace</h2>
      <div className="grid grid-3">
        {agents.map((a: any) => (
          <div key={a.agent_id} className="card">
            <h3>{a.name}</h3>
            <p className="text-sm text-muted mt-2">{a.description?.slice(0, 100)}</p>
            <div className="flex items-center justify-between mt-4">
              <span className="badge badge-info">{a.price_model || 'free'}</span>
              <span className="text-sm text-muted">{a.category}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Billing({ user }: { user: any }) {
  const [balance, setBalance] = useState<any>(null);
  const [usage, setUsage] = useState<any>(null);
  useEffect(() => {
    const tid = user?.tenant_id || '';
    if (tid) {
      api.getBillingBalance(tid).then(setBalance).catch(() => {});
      api.getUsageSummary(tid).then(setUsage).catch(() => {});
    }
  }, [user]);
  return (
    <div>
      <h2 style={{ fontSize: '1.5rem', marginBottom: 20 }}>Billing & Usage</h2>
      <div className="grid grid-2">
        <div className="card">
          <h3>Credit Balance</h3>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: 12, color: 'var(--accent)' }}>
            ${balance?.balance || '0.00'}
          </div>
        </div>
        <div className="card">
          <h3>Usage This Month</h3>
          <div style={{ fontSize: '2rem', fontWeight: 700, marginTop: 12, color: 'var(--success)' }}>
            {usage?.total_calls || 0} calls
          </div>
        </div>
      </div>
    </div>
  );
}