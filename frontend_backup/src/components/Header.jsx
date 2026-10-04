import React, { useState, useEffect } from 'react';
import { Ticket, User, Shield, LogIn, ChevronDown } from 'lucide-react';
import { getSession } from '../data/mockData';

export function Header({ currentRoute = '/', onNavigate, onOpenAuth }) {
  const [session, setLocalSession] = useState(getSession());

  useEffect(() => {
    const handleSessionUpdate = () => setLocalSession(getSession());
    window.addEventListener('fairdrop-session-change', handleSessionUpdate);
    return () => window.removeEventListener('fairdrop-session-change', handleSessionUpdate);
  }, []);

  return (
    <header style={{ backgroundColor: 'var(--bg-primary)', borderBottom: '1px solid var(--border-color)' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px', height: '64px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        {/* Brand Logo */}
        <a
          href="#/"
          onClick={(e) => {
            e.preventDefault();
            onNavigate('/');
          }}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, fontSize: '18px', color: 'var(--text-primary)', letterSpacing: '-0.02em' }}
        >
          <div style={{ width: '32px', height: '32px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--accent-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#FFFFFF' }}>
            <Ticket size={18} />
          </div>
          <span>Fair<span style={{ color: 'var(--accent-primary)' }}>Drop</span></span>
        </a>

        {/* Navigation Links */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: '28px' }}>
          <a
            href="#/"
            onClick={(e) => {
              e.preventDefault();
              onNavigate('/');
            }}
            style={{
              fontSize: '14px',
              fontWeight: currentRoute === '/' ? 600 : 500,
              color: currentRoute === '/' ? 'var(--accent-primary)' : 'var(--text-secondary)',
              borderBottom: currentRoute === '/' ? '2px solid var(--accent-primary)' : '2px solid transparent',
              padding: '20px 0',
              transition: 'color 0.15s ease'
            }}
          >
            Browse Events
          </a>
          <a
            href="#/bookings"
            onClick={(e) => {
              e.preventDefault();
              onNavigate('/bookings');
            }}
            style={{
              fontSize: '14px',
              fontWeight: currentRoute === '/bookings' ? 600 : 500,
              color: currentRoute === '/bookings' ? 'var(--accent-primary)' : 'var(--text-secondary)',
              borderBottom: currentRoute === '/bookings' ? '2px solid var(--accent-primary)' : '2px solid transparent',
              padding: '20px 0',
              transition: 'color 0.15s ease'
            }}
          >
            My Bookings
          </a>
          <a
            href="#/staff"
            onClick={(e) => {
              e.preventDefault();
              onNavigate('/staff');
            }}
            style={{
              fontSize: '14px',
              fontWeight: currentRoute === '/staff' ? 600 : 500,
              color: currentRoute === '/staff' ? 'var(--accent-primary)' : 'var(--text-secondary)',
              borderBottom: currentRoute === '/staff' ? '2px solid var(--accent-primary)' : '2px solid transparent',
              padding: '20px 0',
              transition: 'color 0.15s ease'
            }}
          >
            Staff Portal
          </a>
        </nav>

        {/* User Account / Sign In */}
        <div>
          {session ? (
            <button
              onClick={onOpenAuth}
              className="btn btn-secondary btn-sm"
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--success)' }} className="pulse-clean" />
              <span>{session.user.name}</span>
              {session.user.role === 'admin' && (
                <span className="badge badge-blue" style={{ fontSize: '11px', padding: '1px 5px' }}>
                  Admin
                </span>
              )}
            </button>
          ) : (
            <button
              onClick={onOpenAuth}
              className="btn btn-primary btn-sm"
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <LogIn size={14} />
              <span>Sign In</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
