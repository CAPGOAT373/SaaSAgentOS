import React, { useState } from 'react';
import api from '../services/api';

interface LoginProps {
  onLogin: (token: string, user: any) => void;
}

export default function Login({ onLogin }: LoginProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [tenantId, setTenantId] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      let result;
      if (mode === 'login') {
        if (!tenantId || !email || !password) {
          throw new Error('All fields are required');
        }
        result = await api.login(tenantId, email, password);
      } else {
        if (!tenantId || !username || !email || !password) {
          throw new Error('All fields are required');
        }
        // First create tenant if needed, then register
        try {
          await api.createTenant(username + '_org', tenantId.toLowerCase().replace(/[^a-z0-9-]/g, '-'), 'free');
        } catch (e) {
          // Tenant might already exist, continue
        }
        result = await api.register(tenantId, username, email, password);
        // After register, login
        result = await api.login(tenantId, email, password);
      }

      if (result.access_token) {
        onLogin(result.access_token, result.user || { email, username: username || email });
      } else {
        throw new Error('No access token received');
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      minHeight: '100vh', background: 'var(--bg-primary)',
    }}>
      <div style={{
        width: 420, padding: '40px 32px',
        background: 'var(--bg-secondary)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--accent)' }}>
            Agent OS V6.0
          </h1>
          <p style={{ color: 'var(--text-secondary)', marginTop: 8, fontSize: '0.9rem' }}>
            AI Agent Operating System
          </p>
        </div>

        <div style={{ display: 'flex', marginBottom: 24, borderRadius: 'var(--radius)', overflow: 'hidden', border: '1px solid var(--border)' }}>
          <button
            onClick={() => { setMode('login'); setError(''); }}
            style={{
              flex: 1, padding: '10px', border: 'none', fontSize: '0.9rem', fontWeight: 500,
              background: mode === 'login' ? 'var(--accent)' : 'transparent',
              color: mode === 'login' ? 'white' : 'var(--text-secondary)',
              cursor: 'pointer', transition: 'all 0.2s',
            }}
          >
            Sign In
          </button>
          <button
            onClick={() => { setMode('register'); setError(''); }}
            style={{
              flex: 1, padding: '10px', border: 'none', fontSize: '0.9rem', fontWeight: 500,
              background: mode === 'register' ? 'var(--accent)' : 'transparent',
              color: mode === 'register' ? 'white' : 'var(--text-secondary)',
              cursor: 'pointer', transition: 'all 0.2s',
            }}
          >
            Register
          </button>
        </div>

        {error && (
          <div style={{
            padding: '10px 14px', marginBottom: 16,
            background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--danger)',
            borderRadius: 'var(--radius)', color: 'var(--danger)', fontSize: '0.85rem',
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', marginBottom: 6, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Tenant ID
            </label>
            <input
              type="text"
              placeholder="e.g. my-company"
              value={tenantId}
              onChange={e => setTenantId(e.target.value)}
              style={{ width: '100%' }}
              required
            />
          </div>

          {mode === 'register' && (
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Username
              </label>
              <input
                type="text"
                placeholder="Your name"
                value={username}
                onChange={e => setUsername(e.target.value)}
                style={{ width: '100%' }}
                required
              />
            </div>
          )}

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', marginBottom: 6, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Email
            </label>
            <input
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              style={{ width: '100%' }}
              required
            />
          </div>

          <div style={{ marginBottom: 24 }}>
            <label style={{ display: 'block', marginBottom: 6, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Password
            </label>
            <input
              type="password"
              placeholder="Enter password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              style={{ width: '100%' }}
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary w-full"
            style={{ width: '100%', justifyContent: 'center', opacity: loading ? 0.7 : 1 }}
          >
            {loading ? 'Processing...' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>
      </div>
    </div>
  );
}