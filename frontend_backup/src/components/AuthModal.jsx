import React, { useState } from 'react';
import { X, UserCheck, Shield } from 'lucide-react';
import { getSession, setSession } from '../data/mockData';

export function AuthModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  const currentSession = getSession();
  const [role, setRole] = useState(currentSession?.user?.role || 'user');
  const [name, setName] = useState(currentSession?.user?.name || '');
  const [email, setEmail] = useState(currentSession?.user?.email || '');
  const [password, setPassword] = useState('');
  const [isLogin, setIsLogin] = useState(true);

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      const endpoint = isLogin ? '/login' : '/register';
      const res = await fetch(`http://localhost:3001/api/auth${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();

      if (!res.ok) {
        alert(data.error);
        return;
      }

      if (isLogin) {
        setSession({
          user: data.user,
          token: data.token
        });
        onClose();
      } else {
        alert('Account created successfully! Please log in.');
        setIsLogin(true);
      }
    } catch (err) {
      alert("Could not connect to the backend server.");
    }
  };

  const handleQuickSwitch = (selectedRole) => {
    setRole(selectedRole);
    if (selectedRole === 'admin') {
      setEmail('sysadmin@fairdrop.com');
      setPassword('admin123'); // Preset for the hackathon
      setIsLogin(true);
    } else {
      setEmail('');
      setPassword('');
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(37, 43, 54, 0.4)', padding: '16px' }}>
      <div className="card" style={{ width: '100%', maxWidth: '420px', padding: '24px', position: 'relative' }}>
        <button
          onClick={onClose}
          style={{ position: 'absolute', top: '16px', right: '16px', border: 'none', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer', padding: '4px' }}
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)' }}>Account Settings</h2>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Log in or sign up to access the live drops.
        </p>

        {/* Role Selector Tabs */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '16px' }}>
          <button
            type="button"
            onClick={() => handleQuickSwitch('user')}
            className={`btn ${role === 'user' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            <UserCheck size={15} /> Attendee
          </button>
          <button
            type="button"
            onClick={() => handleQuickSwitch('admin')}
            className={`btn ${role === 'admin' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            <Shield size={15} /> Staff Admin
          </button>
        </div>

        <div style={{ display: 'flex', gap: '8px', marginTop: '16px', justifyContent: 'center' }}>
          {role === 'user' && (
            <>
              <button type="button" style={{ background: 'none', border: 'none', color: isLogin ? 'var(--text-primary)' : 'var(--text-secondary)', fontWeight: isLogin ? 'bold' : 'normal', cursor: 'pointer' }} onClick={() => setIsLogin(true)}>Login</button>
              <span style={{ color: 'var(--text-secondary)' }}>|</span>
              <button type="button" style={{ background: 'none', border: 'none', color: !isLogin ? 'var(--text-primary)' : 'var(--text-secondary)', fontWeight: !isLogin ? 'bold' : 'normal', cursor: 'pointer' }} onClick={() => setIsLogin(false)}>Sign Up</button>
            </>
          )}
        </div>

        <form onSubmit={handleSave} style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '4px' }}>
              Email Address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="alex@example.com"
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '4px' }}>
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          <div style={{ paddingTop: '8px' }}>
            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', padding: '10px' }}
            >
              {isLogin ? 'Log In' : 'Create Account'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
