import React, { useState, useEffect, useRef } from 'react';
import api from '../services/api';
import wsService from '../services/websocket';

interface Agent {
  agent_id: string;
  name: string;
  description: string;
  agent_type?: string;
  price_model?: string;
  category?: string;
  status?: string;
  tenant_id?: string;
}

export default function AgentStudio({ user }: { user: any }) {
  // Agent list
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(false);

  // Create/Edit form
  const [showCreate, setShowCreate] = useState(false);
  const [formName, setFormName] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formType, setFormType] = useState('chat');
  const [formPrompt, setFormPrompt] = useState('');
  const [formCategory, setFormCategory] = useState('');

  // Run agent
  const [runInput, setRunInput] = useState('');
  const [runOutput, setRunOutput] = useState('');
  const [runStreaming, setRunStreaming] = useState(false);
  const [runError, setRunError] = useState('');
  const [runExecId, setRunExecId] = useState('');
  const [runTokens, setRunTokens] = useState(0);
  const [runLatency, setRunLatency] = useState(0);
  const outputRef = useRef<HTMLDivElement>(null);

  // Execution history
  const [executions, setExecutions] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  // Load agents
  const loadAgents = async () => {
    setLoading(true);
    try {
      const data = await api.listAgents(user?.tenant_id);
      setAgents(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error('Failed to load agents:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAgents();
  }, [user?.tenant_id]);

  // Scroll output to bottom
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [runOutput]);

  // Create agent
  const handleCreate = async () => {
    if (!formName.trim()) return;
    try {
      await api.registerAgent({
        tenant_id: user?.tenant_id || '',
        owner_id: user?.user_id || '',
        name: formName,
        description: formDesc,
        agent_type: formType,
        system_prompt: formPrompt,
        category: formCategory,
        price_model: 'free',
        price: 0,
      });
      setShowCreate(false);
      setFormName(''); setFormDesc(''); setFormPrompt(''); setFormCategory('');
      await loadAgents();
    } catch (e: any) {
      alert('Failed to create agent: ' + (e.message || 'Unknown error'));
    }
  };

  // Run agent via WebSocket streaming
  const handleRun = () => {
    if (!selectedAgent || !runInput.trim()) return;
    setRunOutput('');
    setRunError('');
    setRunStreaming(true);
    setRunTokens(0);
    setRunLatency(0);

    // Use WebSocket for real-time streaming
    const ws = new WebSocket(
      (window.location.protocol === 'https:' ? 'wss:' : 'ws:') +
      `//${window.location.host}/ws/agent/execute`
    );

    ws.onopen = () => {
      ws.send(JSON.stringify({
        agent_id: selectedAgent.agent_id,
        user_input: runInput,
        user_id: user?.user_id || '',
        tenant_id: user?.tenant_id || '',
      }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        switch (data.type) {
          case 'execution_started':
            setRunExecId(data.execution_id);
            break;
          case 'prompt_built':
            break;
          case 'token':
            setRunOutput(prev => prev + data.content);
            setRunTokens(prev => prev + 1);
            break;
          case 'execution_completed':
            setRunStreaming(false);
            setRunLatency(data.latency_ms || 0);
            if (data.total_tokens) setRunTokens(data.total_tokens);
            ws.close();
            break;
          case 'execution_failed':
            setRunStreaming(false);
            setRunError(data.error || 'Execution failed');
            ws.close();
            break;
          case 'error':
            setRunStreaming(false);
            setRunError(data.message || 'Unknown error');
            ws.close();
            break;
        }
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    ws.onerror = () => {
      setRunStreaming(false);
      setRunError('WebSocket connection failed');
    };

    ws.onclose = () => {
      setRunStreaming(false);
    };
  };

  // Load executions
  const loadExecutions = async () => {
    if (!selectedAgent) return;
    try {
      const data = await api.getAgentExecutions(selectedAgent.agent_id);
      setExecutions(Array.isArray(data) ? data : []);
      setShowHistory(true);
    } catch (e) {
      console.error('Failed to load executions:', e);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <h2 style={{ fontSize: '1.5rem' }}>Agent Studio</h2>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          + New Agent
        </button>
      </div>

      {/* Create Agent Modal */}
      {showCreate && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
        }}>
          <div className="card" style={{ width: 520, maxHeight: '90vh', overflow: 'auto' }}>
            <h3 style={{ marginBottom: 20 }}>Create New Agent</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ display: 'block', marginBottom: 4, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Name *</label>
                <input value={formName} onChange={e => setFormName(e.target.value)} placeholder="Agent name" style={{ width: '100%' }} />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: 4, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Description</label>
                <textarea value={formDesc} onChange={e => setFormDesc(e.target.value)} placeholder="What does this agent do?" rows={2} style={{ width: '100%' }} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <div>
                  <label style={{ display: 'block', marginBottom: 4, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Type</label>
                  <select value={formType} onChange={e => setFormType(e.target.value)} style={{ width: '100%' }}>
                    <option value="chat">Chat</option>
                    <option value="task">Task</option>
                    <option value="workflow">Workflow</option>
                    <option value="tool">Tool</option>
                    <option value="hybrid">Hybrid</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: 4, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Category</label>
                  <input value={formCategory} onChange={e => setFormCategory(e.target.value)} placeholder="e.g. customer-support" style={{ width: '100%' }} />
                </div>
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: 4, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>System Prompt</label>
                <textarea
                  value={formPrompt}
                  onChange={e => setFormPrompt(e.target.value)}
                  placeholder="You are a helpful AI agent..."
                  rows={4}
                  style={{ width: '100%', fontFamily: 'monospace', fontSize: '0.85rem' }}
                />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleCreate}>Create Agent</button>
            </div>
          </div>
        </div>
      )}

      {/* Execution History Modal */}
      {showHistory && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
        }}>
          <div className="card" style={{ width: 600, maxHeight: '80vh', overflow: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3>Execution History</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setShowHistory(false)}>Close</button>
            </div>
            {executions.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 20 }}>No executions yet</div>
            ) : (
              executions.map((exe: any) => (
                <div key={exe.execution_id} style={{
                  padding: '10px 12px', borderBottom: '1px solid var(--border)',
                  marginBottom: 8,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span className={`badge ${exe.status === 'completed' ? 'badge-success' : exe.status === 'failed' ? 'badge-danger' : 'badge-warning'}`}>
                      {exe.status}
                    </span>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {exe.total_tokens || 0} tokens | {exe.latency_ms?.toFixed(0) || 0}ms
                    </span>
                  </div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
                    Input: {exe.input?.slice(0, 100)}
                  </div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>
                    Output: {exe.output?.slice(0, 200)}
                  </div>
                  {exe.error && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--danger)', marginTop: 4 }}>
                      Error: {exe.error}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 16, height: 'calc(100vh - 160px)' }}>
        {/* Agent List */}
        <div className="card" style={{ overflow: 'auto' }}>
          <h3 style={{ fontSize: '0.95rem', marginBottom: 12, color: 'var(--text-secondary)' }}>Agents</h3>
          {loading && <div style={{ color: 'var(--text-muted)', padding: 12 }}>Loading...</div>}
          {!loading && agents.length === 0 && (
            <div style={{ color: 'var(--text-muted)', padding: 12, fontSize: '0.85rem' }}>
              No agents yet. Create your first agent!
            </div>
          )}
          {agents.map(agent => (
            <div
              key={agent.agent_id}
              onClick={() => setSelectedAgent(agent)}
              style={{
                padding: '12px', borderRadius: 'var(--radius)', cursor: 'pointer',
                marginBottom: 6, transition: 'all 0.15s',
                background: selectedAgent?.agent_id === agent.agent_id ? 'var(--bg-hover)' : 'transparent',
                border: selectedAgent?.agent_id === agent.agent_id ? '1px solid var(--accent)' : '1px solid transparent',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{agent.name}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {agent.description || 'No description'}
              </div>
              <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                <span className="badge badge-info" style={{ fontSize: '0.7rem' }}>{agent.agent_type || 'chat'}</span>
                {agent.category && <span className="badge" style={{ fontSize: '0.7rem', background: 'rgba(255,255,255,0.05)' }}>{agent.category}</span>}
              </div>
            </div>
          ))}
        </div>

        {/* Agent Detail & Run */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {!selectedAgent ? (
            <div className="card" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: '3rem', marginBottom: 12 }}>◆</div>
                <div>Select an agent from the list or create a new one</div>
              </div>
            </div>
          ) : (
            <>
              {/* Agent Info */}
              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h3 style={{ fontSize: '1.1rem' }}>{selectedAgent.name}</h3>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 4 }}>
                      {selectedAgent.description || 'No description'}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button className="btn btn-secondary btn-sm" onClick={loadExecutions}>History</button>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                  <span className="badge badge-info">ID: {selectedAgent.agent_id?.slice(0, 8)}...</span>
                  <span className="badge" style={{ background: 'rgba(255,255,255,0.05)' }}>{selectedAgent.agent_type || 'chat'}</span>
                  {selectedAgent.category && <span className="badge" style={{ background: 'rgba(255,255,255,0.05)' }}>{selectedAgent.category}</span>}
                </div>
              </div>

              {/* Run Area */}
              <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <h3 style={{ fontSize: '0.95rem', marginBottom: 12, color: 'var(--text-secondary)' }}>Run Agent</h3>

                <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
                  <input
                    value={runInput}
                    onChange={e => setRunInput(e.target.value)}
                    placeholder="Enter your message..."
                    style={{ flex: 1 }}
                    onKeyDown={e => e.key === 'Enter' && !runStreaming && handleRun()}
                    disabled={runStreaming}
                  />
                  <button
                    className="btn btn-primary"
                    onClick={handleRun}
                    disabled={runStreaming || !runInput.trim()}
                  >
                    {runStreaming ? 'Running...' : 'Run'}
                  </button>
                </div>

                {/* Streaming Output */}
                <div
                  ref={outputRef}
                  style={{
                    flex: 1, background: 'var(--bg-primary)', borderRadius: 'var(--radius)',
                    padding: 16, overflow: 'auto', fontFamily: 'monospace', fontSize: '0.9rem',
                    minHeight: 200, border: '1px solid var(--border)',
                    whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  }}
                >
                  {!runOutput && !runStreaming && !runError && (
                    <div style={{ color: 'var(--text-muted)' }}>
                      Output will appear here...
                    </div>
                  )}
                  {runOutput}
                  {runStreaming && (
                    <span style={{
                      display: 'inline-block', width: 8, height: 16,
                      background: 'var(--accent)', animation: 'blink 1s infinite',
                      verticalAlign: 'middle', marginLeft: 2,
                    }} />
                  )}
                  {runError && (
                    <div style={{ color: 'var(--danger)' }}>
                      Error: {runError}
                    </div>
                  )}
                </div>

                {/* Stats */}
                {(runTokens > 0 || runLatency > 0 || runExecId) && (
                  <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    {runExecId && <span>Execution: {runExecId.slice(0, 8)}...</span>}
                    <span>Tokens: {runTokens}</span>
                    {runLatency > 0 && <span>Latency: {runLatency.toFixed(0)}ms</span>}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}