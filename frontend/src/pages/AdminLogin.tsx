import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export const AdminLogin: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleLogin = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:3001'}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (res.ok) {
        if (data.user.role === 'admin') {
          login(data.token, data.user);
          navigate('/fairdrop-staff/dashboard');
        } else {
          alert('Access Denied. You do not have admin privileges.');
        }
      } else {
        alert(data.error || 'Invalid credentials');
      }
    } catch (e) {
      alert('Error connecting to the server.');
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex justify-center mb-6">
          <div className="bg-red-500/20 text-red-500 p-4 rounded-full">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
          </div>
        </div>
        <h2 className="text-2xl font-bold mb-2 text-center text-white">Staff Portal</h2>
        <p className="text-slate-400 text-center mb-8">Restricted access for Fair Drop administrators.</p>
        
        <input 
          className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 mb-4 focus:outline-none focus:ring-2 focus:ring-red-500 text-white"
          placeholder="Admin Email" 
          value={email} onChange={e => setEmail(e.target.value)} 
        />
        <input 
          className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 mb-8 focus:outline-none focus:ring-2 focus:ring-red-500 text-white"
          placeholder="Admin Password" 
          type="password"
          value={password} onChange={e => setPassword(e.target.value)} 
          onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
        />
        
        <button 
          onClick={handleLogin}
          className="w-full bg-red-600 hover:bg-red-700 py-3 rounded-lg font-bold transition-colors shadow-lg shadow-red-600/30"
        >
          Secure Login
        </button>
      </div>
    </div>
  );
};
