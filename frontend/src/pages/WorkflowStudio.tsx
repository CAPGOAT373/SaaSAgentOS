import React, { useState, useEffect } from 'react';
import api from '../services/api';
import wsService from '../services/websocket';

interface Workflow {
  workflow_id: string;
  name: string;
  description: string;
  status: string;
  nodes: WorkflowNode[];
  created_at: string;
}

interface WorkflowNode {
  node_id: string;
  name: string;
  node_type: string;
  config: Record<string, any>;
  depends_on: string[];
}

interface ExecutionResult {
  execution_id: string;
  workflow_id: string;
  status: string;
  node_results: Record<string, { status: string; result?: any; error?: string }>;
  started_at: string;
  completed_at: string;
  error: string;
}

export default function WorkflowStudio({ user }: { user: any }) {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState<Workflow | null>(null);
  const [loading, setLoading] = useState(false);

  // Create workflow
  const [showCreate, setShowCreate] = useState(false);
  const [wfName, setWfName] = useState('');
  const [wfDesc, setWfDesc] = useState('');

  // Run workflow
  const [runInput, setRunInput] = useState('{}');
  const [runResult, setRunResult] = useState<ExecutionResult | null>(null);
  const [runRunning, setRunRunning] = useState(false);
  const [runError, setRunError] = useState('');

  // Debug view
  const [debugNode, setDebugNode] = useState<string | null>(null);

  const loadWorkflows = async () => {
    setLoading(true);
    try {
      const data = await api.getWorkflow('list'); // Will fallback
      setWorkflows([]);
    } catch (e) {
      // Workflow list endpoint doesn't exist yet, try direct
      setWorkflows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorkflows();
  }, []);

  const handleCreate = async () => {
    if (!wfName.trim()) return;
    try {
      const result = await api.createWorkflow(wfName, wfDesc, user?.tenant_id || '');
      setShowCreate(false);
      setWfName(''); setWfDesc('');
      // Reload workflows
      if (result) {
        setWorkflows(prev => [...prev, result]);
        setSelectedWorkflow(result);
      }
    } catch (e: any) {
      alert('Failed to create workflow: ' + (e.message || 'Unknown error'));
    }
  };

  const handleRun = async () => {
    if (!selectedWorkflow) return;
    setRunRunning(true);
    setRunError('');
    setRunResult(null);

    try {
      let inputData = {};
      try {
        inputData = JSON.parse(runInput);
      } catch {
        inputData = { input: runInput };
      }

      const result = await api.runWorkflow(selectedWorkflow.workflow_id, inputData);
      setRunResult(result);
    } catch (e: any) {
      setRunError(e.message || 'Workflow execution failed');
    } finally {
      setRunRunning(false);
    }
  };

  const getNodeColor = (type: string) => {
    switch (type) {
      case 'agent': return 'var(--accent)';
      case 'tool': return 'var(--warning)';
      case 'condition': return '#a855f7';
      case 'parallel': return 'var(--success)';
      case 'code': return '#06b6d4';
      case 'http': return '#f97316';
      case 'delay': return 'var(--text-muted)';
      default: return 'var(--text-secondary)';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'var(--success)';
      case 'running': return 'var(--warning)';
      case 'failed': return 'var(--danger)';
      case 'skipped': return 'var(--text-muted)';
      default: return 'var(--text-secondary)';
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <h2 style={{ fontSize: '1.5rem' }}>Workflow Studio</h2>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          + New Workflow
        </button>
      </div>

      {/* Create Workflow Modal */}
      {showCreate && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
        }}>
          <div className="card" style={{ width: 480 }}>
            <h3 style={{ marginBottom: 20 }}>Create New Workflow</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ display: 'block', marginBottom: 4, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Name *</label>
                <input value={wfName} onChange={e => setWfName(e.target.value)} placeholder="Workflow name" style={{ width: '100%' }} />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: 4, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Description</label>
                <textarea value={wfDesc} onChange={e => setWfDesc(e.target.value)} placeholder="What does this workflow do?" rows={3} style={{ width: '100%' }} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleCreate}>Create Workflow</button>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 16, height: 'calc(100vh - 160px)' }}>
        {/* Workflow List */}
        <div className="card" style={{ overflow: 'auto' }}>
          <h3 style={{ fontSize: '0.95rem', marginBottom: 12, color: 'var(--text-secondary)' }}>Workflows</h3>
          {loading && <div style={{ color: 'var(--text-muted)', padding: 12 }}>Loading...</div>}
          {!loading && workflows.length === 0 && (
            <div style={{ color: 'var(--text-muted)', padding: 12, fontSize: '0.85rem' }}>
              No workflows yet. Create your first workflow!
            </div>
          )}
          {workflows.map(wf => (
            <div
              key={wf.workflow_id}
              onClick={() => setSelectedWorkflow(wf)}
              style={{
                padding: '12px', borderRadius: 'var(--radius)', cursor: 'pointer',
                marginBottom: 6, transition: 'all 0.15s',
                background: selectedWorkflow?.workflow_id === wf.workflow_id ? 'var(--bg-hover)' : 'transparent',
                border: selectedWorkflow?.workflow_id === wf.workflow_id ? '1px solid var(--accent)' : '1px solid transparent',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{wf.name}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: 2 }}>
                {wf.description || 'No description'}
              </div>
              <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                <span className={`badge ${wf.status === 'completed' ? 'badge-success' : wf.status === 'running' ? 'badge-warning' : 'badge-info'}`}>
                  {wf.status || 'draft'}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {wf.nodes?.length || 0} nodes
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Workflow Detail */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {!selectedWorkflow ? (
            <div className="card" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: '3rem', marginBottom: 12 }}>◇</div>
                <div>Select a workflow or create a new one</div>
              </div>
            </div>
          ) : (
            <>
              {/* Workflow Info */}
              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h3 style={{ fontSize: '1.1rem' }}>{selectedWorkflow.name}</h3>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 4 }}>
                      {selectedWorkflow.description || 'No description'}
                    </p>
                  </div>
                  <span className={`badge ${selectedWorkflow.status === 'completed' ? 'badge-success' : 'badge-info'}`}>
                    {selectedWorkflow.status || 'draft'}
                  </span>
                </div>
              </div>

              {/* DAG Visualization */}
              <div className="card">
                <h3 style={{ fontSize: '0.95rem', marginBottom: 12, color: 'var(--text-secondary)' }}>
                  DAG Visualization ({selectedWorkflow.nodes?.length || 0} nodes)
                </h3>
                <div style={{
                  background: 'var(--bg-primary)', borderRadius: 'var(--radius)',
                  padding: 20, minHeight: 200, overflow: 'auto',
                  border: '1px solid var(--border)',
                }}>
                  {(!selectedWorkflow.nodes || selectedWorkflow.nodes.length === 0) ? (
                    <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 40 }}>
                      No nodes defined in this workflow. Add nodes to visualize the DAG.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                      {selectedWorkflow.nodes.map((node, idx) => (
                        <React.Fragment key={node.node_id}>
                          {idx > 0 && (
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                              <div style={{ width: 2, height: 20, background: 'var(--border)' }} />
                              <div style={{
                                width: 0, height: 0,
                                borderLeft: '6px solid transparent',
                                borderRight: '6px solid transparent',
                                borderTop: '6px solid var(--border)',
                              }} />
                            </div>
                          )}
                          <div
                            onClick={() => setDebugNode(debugNode === node.node_id ? null : node.node_id)}
                            style={{
                              padding: '10px 20px', borderRadius: 'var(--radius)',
                              background: 'var(--bg-card)', border: `2px solid ${getNodeColor(node.node_type)}`,
                              cursor: 'pointer', minWidth: 180, textAlign: 'center',
                              transition: 'all 0.2s',
                              boxShadow: debugNode === node.node_id ? `0 0 12px ${getNodeColor(node.node_type)}40` : 'none',
                            }}
                          >
                            <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{node.name}</div>
                            <div style={{ fontSize: '0.75rem', color: getNodeColor(node.node_type), marginTop: 2 }}>
                              {node.node_type}
                            </div>
                            {runResult?.node_results?.[node.node_id] && (
                              <div style={{ marginTop: 4 }}>
                                <span style={{
                                  display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                                  background: getStatusColor(runResult.node_results[node.node_id].status),
                                }} />
                              </div>
                            )}
                          </div>

                          {/* Debug Panel */}
                          {debugNode === node.node_id && (
                            <div className="card" style={{ width: '100%', marginTop: 4 }}>
                              <h4 style={{ fontSize: '0.85rem', marginBottom: 8 }}>Node Detail: {node.name}</h4>
                              <div style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: 4 }}>
                                <div><span style={{ color: 'var(--text-muted)' }}>Type:</span> {node.node_type}</div>
                                <div><span style={{ color: 'var(--text-muted)' }}>Config:</span> {JSON.stringify(node.config)}</div>
                                <div><span style={{ color: 'var(--text-muted)' }}>Depends On:</span> {node.depends_on?.join(', ') || 'None'}</div>
                                {runResult?.node_results?.[node.node_id] && (
                                  <>
                                    <div style={{ marginTop: 4, paddingTop: 4, borderTop: '1px solid var(--border)' }}>
                                      <span style={{ color: 'var(--text-muted)' }}>Execution Status:</span>{' '}
                                      <span style={{ color: getStatusColor(runResult.node_results[node.node_id].status) }}>
                                        {runResult.node_results[node.node_id].status}
                                      </span>
                                    </div>
                                    {runResult.node_results[node.node_id].error && (
                                      <div style={{ color: 'var(--danger)' }}>
                                        Error: {runResult.node_results[node.node_id].error}
                                      </div>
                                    )}
                                    {runResult.node_results[node.node_id].result && (
                                      <div style={{ color: 'var(--text-primary)', wordBreak: 'break-all' }}>
                                        Result: {JSON.stringify(runResult.node_results[node.node_id].result).slice(0, 200)}
                                      </div>
                                    )}
                                  </>
                                )}
                              </div>
                            </div>
                          )}
                        </React.Fragment>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Run Controls */}
              <div className="card">
                <h3 style={{ fontSize: '0.95rem', marginBottom: 12, color: 'var(--text-secondary)' }}>Execute Workflow</h3>
                <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
                  <textarea
                    value={runInput}
                    onChange={e => setRunInput(e.target.value)}
                    placeholder='{"key": "value"}'
                    rows={2}
                    style={{ flex: 1, fontFamily: 'monospace', fontSize: '0.85rem' }}
                  />
                  <button
                    className="btn btn-primary"
                    onClick={handleRun}
                    disabled={runRunning}
                    style={{ alignSelf: 'flex-start' }}
                  >
                    {runRunning ? 'Running...' : 'Run Workflow'}
                  </button>
                </div>

                {runError && (
                  <div style={{
                    padding: 10, borderRadius: 'var(--radius)',
                    background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--danger)',
                    color: 'var(--danger)', fontSize: '0.85rem', marginBottom: 12,
                  }}>
                    {runError}
                  </div>
                )}

                {runResult && (
                  <div style={{
                    background: 'var(--bg-primary)', borderRadius: 'var(--radius)',
                    padding: 16, border: '1px solid var(--border)',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                      <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Execution Result</span>
                      <span className={`badge ${runResult.status === 'completed' ? 'badge-success' : runResult.status === 'failed' ? 'badge-danger' : 'badge-warning'}`}>
                        {runResult.status}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 8 }}>
                      ID: {runResult.execution_id?.slice(0, 8)}... | Nodes: {Object.keys(runResult.node_results || {}).length}
                    </div>
                    {runResult.error && (
                      <div style={{ color: 'var(--danger)', fontSize: '0.85rem', marginBottom: 8 }}>
                        Error: {runResult.error}
                      </div>
                    )}
                    {Object.keys(runResult.node_results || {}).length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {Object.entries(runResult.node_results).map(([nodeId, result]) => (
                          <div key={nodeId} style={{
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            padding: '6px 10px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius)',
                            fontSize: '0.8rem',
                          }}>
                            <span style={{ color: 'var(--text-secondary)' }}>{nodeId.slice(0, 8)}...</span>
                            <span style={{ color: getStatusColor(result.status) }}>{result.status}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}