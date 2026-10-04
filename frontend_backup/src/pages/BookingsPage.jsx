import React, { useState, useEffect } from 'react';
import { Calendar, MapPin, Ticket, CheckCircle } from 'lucide-react';
import { getBookings } from '../data/mockData';

export function BookingsPage({ onNavigate }) {
  const [bookings, setBookings] = useState(getBookings());

  useEffect(() => {
    const handleUpdate = () => setBookings(getBookings());
    window.addEventListener('fairdrop-bookings-change', handleUpdate);
    return () => window.removeEventListener('fairdrop-bookings-change', handleUpdate);
  }, []);

  return (
    <main style={{ maxWidth: '900px', margin: '0 auto', padding: '48px 24px 80px 24px' }}>
      {/* Page Header */}
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
          My Bookings
        </h1>
        <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Every confirmed seat, all in one place.
        </p>
      </div>

      {/* Bookings List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {bookings.map((booking) => (
          <div
            key={booking.id}
            className="card"
            style={{ padding: '24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '24px', flexWrap: 'wrap' }}
          >
            {/* Left: Info */}
            <div style={{ flex: 1, minWidth: '200px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <span className="badge badge-green">
                  <CheckCircle size={12} />
                  {booking.status}
                </span>
                {booking.seats > 1 && (
                  <span className="badge badge-blue">{booking.seats} Tickets</span>
                )}
              </div>

              <h2 style={{ fontSize: '17px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
                {booking.event_name || 'FairDrop Event'}
              </h2>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '5px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Calendar size={13} style={{ color: 'var(--accent-primary)', flexShrink: 0 }} />
                  <span>{booking.date || 'Saturday · 8:00 PM'}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <MapPin size={13} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />
                  <span>{booking.venue || 'Main Venue, Mumbai'}</span>
                </div>
              </div>
            </div>

            {/* Right: Ticket Code + Total */}
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px', marginBottom: '6px' }}>
                <Ticket size={16} style={{ color: 'var(--accent-primary)' }} />
                <span style={{ fontFamily: 'monospace', fontSize: '13px', fontWeight: 600, color: 'var(--accent-primary)', letterSpacing: '0.05em' }}>
                  {booking.ticketCode || `FD-${booking.id}`}
                </span>
              </div>
              {booking.totalAmount && (
                <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {booking.totalAmount}
                </div>
              )}
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px', textTransform: 'uppercase', fontWeight: 500 }}>
                Booking ID: {booking.id}
              </div>
            </div>
          </div>
        ))}

        {/* Empty State */}
        {bookings.length === 0 && (
          <div className="card" style={{ padding: '64px 32px', textAlign: 'center' }}>
            <div style={{ width: '56px', height: '56px', borderRadius: 'var(--radius-lg)', backgroundColor: 'var(--accent-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px auto', color: 'var(--accent-primary)' }}>
              <Ticket size={24} />
            </div>
            <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)' }}>No tickets yet</h2>
            <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '6px' }}>
              Your next fair win starts with a live drop.
            </p>
            <button
              onClick={() => onNavigate('/')}
              className="btn btn-primary"
              style={{ marginTop: '20px' }}
            >
              Browse Events
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
