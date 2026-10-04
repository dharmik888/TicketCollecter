import React, { useState } from 'react';
import { Calendar, MapPin, Users, ArrowLeft, ShieldCheck, Ticket, Info, CheckCircle2 } from 'lucide-react';
import { getEvents, getSession } from '../data/mockData';

export function EventDetailPage({ eventId, onNavigate }) {
  const events = getEvents();
  const event = events.find((e) => e.id === eventId) || events[0];
  const session = getSession();

  const [name, setName] = useState(session?.user?.name || 'Alex Rivera');
  const [email, setEmail] = useState(session?.user?.email || 'alex.rivera@example.com');
  const [seatCount, setSeatCount] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const subtotal = event.priceNum * seatCount;

  const handleSubmit = (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    sessionStorage.setItem(
      `fairdrop_registration_${event.id}`,
      JSON.stringify({ name, email, seatCount, eventId: event.id })
    );

    setTimeout(() => {
      setIsSubmitting(false);
      onNavigate(`/queue/${event.id}`);
    }, 300);
  };

  return (
    <main style={{ maxWidth: '1100px', margin: '0 auto', padding: '36px 24px 64px 24px' }}>
      {/* Breadcrumb / Back button */}
      <button
        onClick={() => onNavigate('/')}
        className="btn btn-secondary btn-sm"
        style={{ marginBottom: '24px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
      >
        <ArrowLeft size={14} /> Back to Events
      </button>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '32px', alignItems: 'start' }}>
        {/* Left Column: Event Overview */}
        <div>
          <div className="card" style={{ overflow: 'hidden' }}>
            <div style={{ width: '100%', height: '280px', backgroundColor: 'var(--bg-secondary)', overflow: 'hidden' }}>
              <img
                src={event.image}
                alt={event.name}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            </div>

            <div style={{ padding: '24px' }}>
              <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                <span className="badge badge-blue">{event.tag}</span>
                <span className="badge badge-green">
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--success)' }} className="pulse-clean" />
                  Live Drop
                </span>
              </div>

              <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)' }}>
                {event.name}
              </h1>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '16px', padding: '16px', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)' }}>
                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 500 }}>Date & Time</div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Calendar size={13} style={{ color: 'var(--accent-primary)' }} /> {event.date.split('·')[0]} · {event.date.split('·')[1]}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 500 }}>Location</div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <MapPin size={13} style={{ color: 'var(--accent-primary)' }} /> {event.date.split('·')[2] || 'Main Stage'}
                  </div>
                </div>
              </div>

              <div style={{ marginTop: '20px' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
                  About the Event
                </h3>
                <p style={{ fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                  {event.description}
                </p>
              </div>

              <div style={{ marginTop: '24px', padding: '14px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', backgroundColor: '#FFFFFF', display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                <ShieldCheck size={18} style={{ color: 'var(--success)', flexShrink: 0, marginTop: '2px' }} />
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  <strong style={{ color: 'var(--text-primary)' }}>Verified Fan Protection:</strong> All tickets are digitally encrypted to your account to prevent unauthorized re-listing.
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Ticket Registration Form */}
        <div>
          <div className="card" style={{ padding: '28px', position: 'sticky', top: '88px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '16px', borderBottom: '1px solid var(--border-color)' }}>
              <div>
                <span className="badge badge-grey">Step 1 of 3</span>
                <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '4px' }}>
                  Attendee Details
                </h2>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Price per Ticket</div>
                <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--accent-primary)' }}>{event.price}</div>
              </div>
            </div>

            <form onSubmit={handleSubmit} style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '6px' }}>
                  Full Name (Primary Attendee)
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Alex Rivera"
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '6px' }}>
                  Email Address (For e-Ticket Delivery)
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '6px' }}>
                  Ticket Quantity
                </label>
                <select
                  value={seatCount}
                  onChange={(e) => setSeatCount(Number(e.target.value))}
                  style={{ cursor: 'pointer' }}
                >
                  <option value={1}>1 Ticket — ₹{event.priceNum.toLocaleString('en-IN')}</option>
                  <option value={2}>2 Tickets — ₹{(event.priceNum * 2).toLocaleString('en-IN')}</option>
                  <option value={3}>3 Tickets — ₹{(event.priceNum * 3).toLocaleString('en-IN')}</option>
                  <option value={4}>4 Tickets (Maximum) — ₹{(event.priceNum * 4).toLocaleString('en-IN')}</option>
                </select>
              </div>

              {/* Order Calculation Preview */}
              <div style={{ padding: '12px 16px', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '13px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Estimated Subtotal:</span>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '15px' }}>
                  ₹{subtotal.toLocaleString('en-IN')}
                </span>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="btn btn-primary btn-lg"
                style={{ width: '100%', marginTop: '8px' }}
              >
                {isSubmitting ? (
                  <>
                    <span className="spin-clean" style={{ display: 'inline-block', width: '14px', height: '14px', border: '2px solid #FFFFFF', borderTopColor: 'transparent', borderRadius: '50%' }} />
                    Verifying Device Session...
                  </>
                ) : (
                  <>
                    Enter Verified Queue <ArrowRight size={16} />
                  </>
                )}
              </button>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />
                <span>Zero service markups · Transparent queue order</span>
              </div>
            </form>
          </div>
        </div>
      </div>
    </main>
  );
}
