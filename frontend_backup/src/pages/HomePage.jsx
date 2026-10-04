import React, { useState, useEffect } from 'react';
import { Calendar, MapPin, Users, ArrowRight, ShieldCheck, Zap, Lock, Search, Filter } from 'lucide-react';
import { getEvents } from '../data/mockData';

export function HomePage({ onNavigate }) {
  const [events, setEvents] = useState([]);
  const [selectedTag, setSelectedTag] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetch('http://localhost:3001/api/events')
      .then(res => res.json())
      .then(data => setEvents(Array.isArray(data) ? data : []))
      .catch(err => console.error(err));
  }, []);

  const filteredEvents = events.filter((e) => {
    const matchesTag = selectedTag === 'ALL' || e.tag.toUpperCase() === selectedTag;
    const matchesSearch = e.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          e.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          e.date.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTag && matchesSearch;
  });

  return (
    <main style={{ minHeight: 'calc(100vh - 64px)' }}>
      {/* HERO SECTION */}
      <section style={{ backgroundColor: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)', padding: '56px 24px' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          <div style={{ maxWidth: '720px' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', marginBottom: '16px' }} className="badge badge-green">
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--success)' }} className="pulse-clean" />
              <span>Real-Time Fair Queue Active</span>
            </div>

            <h1 style={{ fontSize: '36px', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
              Fair & Transparent Live Event Ticketing
            </h1>

            <p style={{ fontSize: '16px', color: 'var(--text-secondary)', marginTop: '12px', lineHeight: 1.6 }}>
              A bot-resistant queue platform that ensures real fans get fair access to high-demand tickets without scalpers, line-cutting, or inflated prices.
            </p>

            <div style={{ display: 'flex', gap: '12px', marginTop: '24px', flexWrap: 'wrap' }}>
              <button
                onClick={() => {
                  const el = document.getElementById('events-section');
                  if (el) el.scrollIntoView({ behavior: 'smooth' });
                }}
                className="btn btn-primary btn-lg"
              >
                Browse Live Events <ArrowRight size={16} />
              </button>
              <button
                onClick={() => {
                  const el = document.getElementById('how-it-works');
                  if (el) el.scrollIntoView({ behavior: 'smooth' });
                }}
                className="btn btn-secondary btn-lg"
              >
                How Verification Works
              </button>
            </div>
          </div>

          {/* Key Trust Stats Bar */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginTop: '40px', paddingTop: '24px', borderTop: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ width: '36px', height: '36px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--accent-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-primary)' }}>
                <Zap size={18} />
              </div>
              <div>
                <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>Proof-of-Work</div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Automated bot barrier</div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ width: '36px', height: '36px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--success-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--success)' }}>
                <ShieldCheck size={18} />
              </div>
              <div>
                <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>98.4% Integrity</div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Fair FIFO queue order</div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ width: '36px', height: '36px', borderRadius: 'var(--radius-md)', backgroundColor: '#F3F4F6', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-primary)' }}>
                <Lock size={18} />
              </div>
              <div>
                <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>10-Min Hold Window</div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Guaranteed seat checkout</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* EVENTS CATALOG SECTION */}
      <section id="events-section" style={{ maxWidth: '1200px', margin: '0 auto', padding: '48px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', marginBottom: '24px' }}>
          <div>
            <h2 style={{ fontSize: '22px', fontWeight: 600, color: 'var(--text-primary)' }}>Current Event Drops</h2>
            <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '2px' }}>
              Select an event to view details and enter the verified queue room.
            </p>
          </div>

          {/* Filter and Search */}
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ position: 'relative', minWidth: '220px' }}>
              <Search size={15} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-secondary)' }} />
              <input
                type="text"
                placeholder="Search events, artists, venue..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ paddingLeft: '32px', height: '36px', fontSize: '13px' }}
              />
            </div>

            <div style={{ display: 'flex', gap: '6px' }}>
              {['ALL', 'SYNTHWAVE', 'JAZZ', 'COMEDY'].map((tag) => (
                <button
                  key={tag}
                  onClick={() => setSelectedTag(tag)}
                  className={`btn btn-sm ${selectedTag === tag ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ textTransform: 'capitalize', fontSize: '12px' }}
                >
                  {tag === 'ALL' ? 'All' : tag.toLowerCase()}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Events Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '24px' }}>
          {filteredEvents.map((event) => (
            <div key={event.id} className="card" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', transition: 'border-color 0.15s ease' }}>
              {/* Event Image */}
              <div style={{ position: 'relative', width: '100%', height: '190px', backgroundColor: 'var(--bg-secondary)', overflow: 'hidden' }}>
                <img
                  src={event.image}
                  alt={event.name}
                  loading="lazy"
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
                <div style={{ position: 'absolute', top: '12px', left: '12px' }}>
                  <span className="badge badge-blue" style={{ fontWeight: 600, fontSize: '11px', textTransform: 'uppercase' }}>
                    {event.tag}
                  </span>
                </div>
                <div style={{ position: 'absolute', top: '12px', right: '12px' }}>
                  <span className="badge badge-green" style={{ fontSize: '11px' }}>
                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--success)' }} className="pulse-clean" />
                    Queue Open
                  </span>
                </div>
              </div>

              {/* Event Info */}
              <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', flex: 1 }}>
                <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {event.name}
                </h3>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '10px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Calendar size={14} style={{ color: 'var(--accent-primary)' }} />
                    <span>{event.date}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Users size={14} style={{ color: 'var(--text-secondary)' }} />
                    <span>{event.available_seats} of {event.total_seats} seats remaining</span>
                  </div>
                </div>

                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '12px', lineHeight: 1.5, flex: 1, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {event.description}
                </p>

                {/* Card Footer */}
                <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 500 }}>Ticket Price</div>
                    <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>{event.price}</div>
                  </div>

                  <button
                    onClick={() => onNavigate(`/event/${event.id}`)}
                    className="btn btn-primary"
                    style={{ padding: '8px 16px' }}
                  >
                    Select Tickets <ArrowRight size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {filteredEvents.length === 0 && (
          <div className="card" style={{ padding: '48px', textAlign: 'center', marginTop: '16px' }}>
            <p style={{ fontSize: '15px', color: 'var(--text-secondary)' }}>No events match your search criteria.</p>
            <button
              onClick={() => { setSelectedTag('ALL'); setSearchQuery(''); }}
              className="btn btn-secondary btn-sm"
              style={{ marginTop: '12px' }}
            >
              Reset Filters
            </button>
          </div>
        )}
      </section>

      {/* HOW IT WORKS SECTION */}
      <section id="how-it-works" style={{ backgroundColor: 'var(--bg-secondary)', borderTop: '1px solid var(--border-color)', padding: '56px 24px' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          <div style={{ textAlign: 'center', maxWidth: '640px', margin: '0 auto 40px auto' }}>
            <h2 style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)' }}>
              How FairDrop Secures Every Ticket Drop
            </h2>
            <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '8px' }}>
              Our platform uses multi-layered protection to eliminate unfair advantages.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
            <div className="card" style={{ padding: '24px' }}>
              <div style={{ width: '40px', height: '40px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--accent-light)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-primary)', marginBottom: '16px' }}>
                <Zap size={20} />
              </div>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                1. Cryptographic Device Check
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '8px', lineHeight: 1.6 }}>
                Before entering the queue, your browser solves a brief SHA-256 computation. This imperceptible step makes automated multi-bot script attacks computationally unviable.
              </p>
            </div>

            <div className="card" style={{ padding: '24px' }}>
              <div style={{ width: '40px', height: '40px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--success-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--success)', marginBottom: '16px' }}>
                <ShieldCheck size={20} />
              </div>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                2. FIFO Queue Management
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '8px', lineHeight: 1.6 }}>
                Positions are assigned chronologically. Your queue state is backed by secure session tokens so accidental page refreshes do not lose your spot.
              </p>
            </div>

            <div className="card" style={{ padding: '24px' }}>
              <div style={{ width: '40px', height: '40px', borderRadius: 'var(--radius-md)', backgroundColor: '#F3F4F6', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-primary)', marginBottom: '16px' }}>
                <Lock size={20} />
              </div>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                3. Dedicated Checkout Window
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '8px', lineHeight: 1.6 }}>
                When you reach the front of the queue, your selected tickets are reserved for 10 minutes, giving you adequate time to enter payment without pressure.
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
