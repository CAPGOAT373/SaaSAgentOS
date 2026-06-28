import React, { useState, useEffect, useRef } from 'react';
import api from '../services/api';
import wsService from '../services/websocket';

interface ExecutionEvent {
  type: string;
  stream?: string;
  event_type?: string;
  data?: any;
  payload?: any;
  timestamp: string;
}

interface SystemStats {
  total_agents: number;
  total_executions: number;
  total_tools: number;
  status: string;
}

export default function CommandCenter({ user }: { user: any }) {
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [stats, setStats] = useState<SystemStats>({ total_agents: 0, total_executions: 0, total_tools: 0, status: 'connecting' });
  const [wsConnected, setWsConnected] = useState(false);
  const [activeExecutions, setActiveExecutions] = useState<Set<string>>(new Set());
  const [tokenUsage, setTokenUsage] = useState(0);
  const [apiLatency, setApiLatency] = useState(0);
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Subscribe to WebSocket events
    const unsubConnection = wsService.on('connection', (d) => {
      setWsConnected(d.status === 'connected');
    });

    const unsubEvent = wsService.on('event', (data) => {
      const event: ExecutionEvent = {
        type: 'event',
        stream: data.stream || data.event_type,
        data: data.data || data.payload,
        timestamp: data.timestamp || new Date().toISOString(),
      };
      setEvents(prev => [event, ...prev].slice(0, 200));

      // Track active executions
      if (data.stream?.includes('execution.started')) {
        setActiveExecutions(prev => new Set(prev).add(data.data?.execution_id || ''));
      }
      if (data.stream?.includes('execution.completed') || data.stream?.includes('execution.failed')) {
        setActiveExecutions(prev => {
          const next = new Set(prev);
          next.delete(data.data?.execution_id || '');
          return next;
        });
      }

      // Track token usage
      if (data.data?.total_tokens) {
        setTokenUsage(prev => prev + data.data.total_tokens);
      }
    });

    const unsubSystem = wsService.on('system_stats', (data) => {
      if (data.data) {
        setStats({
          total_agents: data.data.total_agents || 0,
          total_executions: data.data.total_executions || 0,
          total_tools: data.data.total_tools || 0,
          status: 'healthy',
        });
      }
    });

    // Fetch initial health
    api.getAdminHealth().then(d => {
      const rt = d?.services?.agent_runtime;
      if (rt) {
        setStats({
          total_agents: rt.total_agents || 0,
          total_executions: rt.total_executions || 0,
          total_tools: rt.total_tools || 0,
          status: rt.status || 'healthy',
        });
      }
      setApiLatency(0);
    }).catch(() => {});

    return () => {
      unsubConnection();
      unsubEvent();
      unsubSystem();
    };
  }, []);

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = 0;
    }
  }, [events.length]);

  const formatTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleTimeString();
    } catch {
      return ts;
    }
  };

  const getEventColor = (stream: string) => {
    if (stream?.includes('started') || stream?.includes('running')) return 'var(--warning)';
    if (stream?.includes('completed') || stream?.includes('executed')) return 'var(--success)';
    if (stream?.includes('failed') || stream?.includes('error')) return 'var(--danger)';
    if (stream?.includes('streaming')) return 'var(--accent)';
    return 'var(--text-secondary)';
  };

  const getEventLabel = (stream: string) => {
    return stream?.replace('agent_os.', '').replace('.events', '').replace(/\./g, ' ') || 'event';
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <h2 style={{ fontSize: '1.5rem' }}>Command Center</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            width: 10, height: 10, borderRadius: '50%',
            background: wsConnected ? 'var(--success)' : 'var(--danger)',
            display: 'inline-block',
          }} />
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            {wsConnected ? 'Live' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-4" style={{ marginBottom: 24 }}>
        <div className="card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 8 }}>Total Agents</div>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent)' }}>{stats.total_agents}</div>
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 8 }}>Total Executions</div>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--success)' }}>{stats.total_executions}</div>
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 8 }}>Active Now</div>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--warning)' }}>{activeExecutions.size}</div>
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 8 }}>Token Usage</div>
          <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent)' }}>{tokenUsage.toLocaleString()}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
        {/* Execution Feed */}
        <div className="card" style={{ maxHeight: 'calc(100vh - 340px)', display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ fontSize: '0.95rem', marginBottom: 12, color: 'var(--text-secondary)' }}>
            Live Execution Feed
            <span style={{ fontSize: '0.75rem', marginLeft: 8, color: 'var(--text-muted)' }}>
              ({events.length} events)
            </span>
          </h3>
          <div ref={feedRef} style={{ flex: 1, overflow: 'auto', fontFamily: 'monospace', fontSize: '0.8rem' }}>
            {events.length === 0 && (
              <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 40 }}>
                Waiting for events... Run an agent to see live execution feed.
              </div>
            )}
            {events.map((event, i) => (
              <div
                key={i}
                style={{
                  padding: '6px 10px', borderBottom: '1px solid var(--border)',
                  display: 'flex', gap: 10, alignItems: 'flex-start',
                  opacity: i === 0 ? 1 : 0.7,
                }}
              >
                <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: getEventColor(event.stream || event.event_type || ''),
                  marginTop: 5, flexShrink: 0,
                }} />
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                    <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>
                      {getEventLabel(event.stream || event.event_type || '')}
                    </span>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                      {formatTime(event.timestamp)}
                    </span>
                  </div>
                  <div style={{ color: 'var(--text-primary)', wordBreak: 'break-all' }}>
                    {event.data ? JSON.stringify(event.data).slice(0, 200) : ''}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* System Status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <h3 style={{ fontSize: '0.95rem', marginBottom: 12, color: 'var(--text-secondary)' }}>System Status</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.85rem' }}>Agent Runtime</span>
                <span className="badge badge-success">{stats.status}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.85rem' }}>WebSocket</span>
                <span className={wsConnected ? 'badge badge-success' : 'badge badge-danger'}>
                  {wsConnected ? 'connected' : 'disconnected'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.85rem' }}>Registered Tools</span>
                <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{stats.total_tools}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.85rem' }}>API Latency</span>
                <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>{apiLatency}ms</span>
              </div>
            </div>
          </div>

          <div className="card">
            <h3 style={{ fontSize: '0.95rem', marginBottom: 12, color: 'var(--text-secondary)' }}>Tenant Info</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>ID</span>
                <span style={{ fontSize: '0.85rem' }}>{user?.tenant_id || 'N/A'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>User</span>
                <span style={{ fontSize: '0.85rem' }}>{user?.username || user?.email || 'N/A'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Role</span>
                <span style={{ fontSize: '0.85rem' }}>{user?.roles?.[0] || 'user'}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}