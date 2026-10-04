import React, { useState, useEffect } from 'react';
import { Eye, Play, Plus, Square, X, Shield } from 'lucide-react';
import { getEvents, saveEvents, getSession, setSession } from '../data/mockData';

export function StaffPage({ onNavigate }) {
  const [session, setLocalSession] = useState(getSession());
  const [events, setEventsList] = useState(getEvents());
  const [errorMsg, setErrorMsg] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);

  const [newEventName, setNewEventName] = useState('');
  const [newEventTag, setNewEventTag] = useState('TECH');
  const [newEventSeats, setNewEventSeats] = useState(300);
  const [newEventPrice, setNewEventPrice] = useState('₹999');

  useEffect(() => {
    const handleEventsUpdate = () => setEventsList(getEvents());
    const handleSessionUpdate = () => setLocalSession(getSession());
    window.addEventListener('fairdrop-events-change', handleEventsUpdate);
    window.addEventListener('fairdrop-session-change', handleSessionUpdate);
    return () => {
      window.removeEventListener('fairdrop-events-change', handleEventsUpdate);
      window.removeEventListener('fairdrop-session-change', handleSessionUpdate);
    };
  }, []);

  const handleStaffLogin = (e) => {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const email = data.get('email');

    if (email) {
      setSession({
        user: {
          id: 'adm_staff_001',
          name: 'FairDrop Operations Admin',
          email: String(email),
          role: 'admin'
        },
        token: `tok_admin_${Date.now()}`
      });
      setErrorMsg('');
    } else {
      setErrorMsg('Please enter valid staff credentials.');
    }
  };

  const handleToggleStatus = (id, newStatus) => {
    const updated = events.map((ev) =>
      ev.id === id ? { ...ev, status: newStatus } : ev
    );
    saveEvents(updated);
  };

  const handleCreateEvent = (e) => {
    e.preventDefault();
    if (!newEventName) return;

    const newEv = {
      id: newEventName.toLowerCase().replace(/\s+/g, '-'),
      name: newEventName,
      tag: newEventTag,
      date: 'Sat · 7:30 PM · Arena 1',
      price: newEventPrice,
      priceNum: parseInt(newEventPrice.replace(/[^\d]/g, ''), 10) || 999,
      total_seats: Number(newEventSeats),
      available_seats: Number(newEventSeats),
      duration_minutes: 60,
      status: 'ACTIVE',
      image: '/assets/event-synthwave-BfV0-GEt.jpg',
      description: 'Brand new verified live drop on the Fair Drop platform.'
    };

    saveEvents([...events, newEv]);
    setShowCreateModal(false);
    setNewEventName('');
  };

  const isAdmin = session?.user?.role === 'admin';

  if (!isAdmin) {
    return (
      <main style={{ minHeight: 'calc(100vh - 64px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 24px', backgroundColor: 'var(--bg-secondary)' }}>
        <div style={{ width: '100%', maxWidth: '420px' }}>
          <div style={{ textAlign: 'center', marginBottom: '28px' }}>
            <div style={{ width: '48px', height: '48px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--accent-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px auto', color: 'var(--accent-primary)' }}>
              <Shield size={22} />
            </div>
            <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>Staff Portal</h1>
            <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '4px' }}>Sign in with an administrator account.</p>
          </div>

          <form
            onSubmit={handleStaffLogin}
            className="card"
            style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '16px' }}
          >
            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Email Address
              </label>
              <input
                required
                name="email"
                type="email"
                placeholder="staff@fairdrop.io"
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Password
              </label>
              <input
                required
                name="password"
                type="password"
                placeholder="Enter password"
              />
            </div>

            {errorMsg && (
              <div style={{ padding: '10px 14px', backgroundColor: 'var(--error-bg)', color: 'var(--error)', borderRadius: 'var(--radius-md)', fontSize: '13px' }}>
                {errorMsg}
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary btn-lg"
              style={{ width: '100%', marginTop: '8px' }}
            >
              Open Control Room
            </button>
          </form>
        </div>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '40px 24px 80px 24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', justifyContent: 'space-between', gap: '16px', marginBottom: '32px' }}>
        <div>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--accent-primary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
            Staff Event Control
          </div>
          <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>Live Operations</h1>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn btn-primary"
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <Plus size={16} /> Create Event
        </button>
      </div>

      {/* Metric Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginBottom: '40px' }}>
        {[
          { val: '1,204', label: 'Registered', color: 'var(--accent-primary)' },
          { val: '128', label: 'In Queue', color: 'var(--text-primary)' },
          { val: '96', label: 'Allocated', color: 'var(--success)' },
          { val: '18', label: 'Bots Caught', color: 'var(--error)' },
        ].map(({ val, label, color }) => (
          <div key={label} className="card" style={{ padding: '20px' }}>
            <div style={{ fontSize: '32px', fontWeight: 700, color, letterSpacing: '-0.02em' }}>{val}</div>
            <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginTop: '4px' }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Events Table Section */}
      <section>
        <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '16px' }}>Events</h2>
        <div className="card" style={{ overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: '640px', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ backgroundColor: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)' }}>
                  <th style={{ padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Event</th>
                  <th style={{ padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Seats</th>
                  <th style={{ padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Status</th>
                  <th style={{ padding: '12px 16px', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Controls</th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev, i) => (
                  <tr key={ev.id} style={{ borderTop: i === 0 ? 'none' : '1px solid var(--border-color)' }}>
                    <td style={{ padding: '14px 16px', fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>{ev.name}</td>
                    <td style={{ padding: '14px 16px', fontSize: '14px', color: 'var(--text-secondary)' }}>{ev.total_seats}</td>
                    <td style={{ padding: '14px 16px' }}>
                      <span
                        className={ev.status === 'ACTIVE' ? 'badge badge-green' : 'badge badge-grey'}
                      >
                        {ev.status}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <button
                          onClick={() => handleToggleStatus(ev.id, 'ACTIVE')}
                          title="Open queue"
                          className="btn btn-secondary btn-sm"
                          style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                        >
                          <Play size={13} /> Open
                        </button>
                        <button
                          onClick={() => onNavigate(`/queue/${ev.id}`)}
                          title="View queue room"
                          className="btn btn-secondary btn-sm"
                          style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                        >
                          <Eye size={13} /> View
                        </button>
                        <button
                          onClick={() => handleToggleStatus(ev.id, 'CLOSED')}
                          title="Close queue"
                          className="btn btn-sm"
                          style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', backgroundColor: 'var(--error-bg)', color: 'var(--error)', border: '1px solid var(--error)', borderRadius: 'var(--radius-md)' }}
                        >
                          <Square size={13} /> Close
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Create Event Modal */}
      {showCreateModal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(37, 43, 54, 0.4)', padding: '16px' }}>
          <div className="card" style={{ width: '100%', maxWidth: '440px', padding: '28px', position: 'relative' }}>
            <button
              onClick={() => setShowCreateModal(false)}
              style={{ position: 'absolute', top: '16px', right: '16px', border: 'none', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer', padding: '4px' }}
              aria-label="Close"
            >
              <X size={18} />
            </button>

            <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>Create Live Drop</h2>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '20px' }}>Configure a new drop allocation room.</p>

            <form onSubmit={handleCreateEvent} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '6px' }}>
                  Event Title
                </label>
                <input
                  type="text"
                  required
                  value={newEventName}
                  onChange={(e) => setNewEventName(e.target.value)}
                  placeholder="e.g. Midnight Beats Festival"
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '6px' }}>
                    Genre / Tag
                  </label>
                  <input
                    type="text"
                    required
                    value={newEventTag}
                    onChange={(e) => setNewEventTag(e.target.value.toUpperCase())}
                    placeholder="ELECTRONIC"
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '6px' }}>
                    Total Seats
                  </label>
                  <input
                    type="number"
                    required
                    min={10}
                    value={newEventSeats}
                    onChange={(e) => setNewEventSeats(Number(e.target.value))}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '6px' }}>
                  Ticket Price
                </label>
                <input
                  type="text"
                  required
                  value={newEventPrice}
                  onChange={(e) => setNewEventPrice(e.target.value)}
                  placeholder="₹1,299"
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary btn-lg"
                style={{ width: '100%', marginTop: '4px' }}
              >
                Publish Drop Room
              </button>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
