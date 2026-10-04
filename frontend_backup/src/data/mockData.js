const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || 'http://localhost:3001';

export const INITIAL_EVENTS = [
  {
    id: 'neon-night',
    name: 'Neon Night Market',
    tag: 'SYNTHWAVE',
    date: 'Sat · 8:00 PM · Warehouse 9',
    price: '₹1,499',
    priceNum: 1499,
    total_seats: 500,
    available_seats: 84,
    duration_minutes: 90,
    status: 'ACTIVE',
    image: '/assets/event-synthwave-BfV0-GEt.jpg',
    description: 'An immersive retro-futuristic audio-visual experience with live synthwave artists, neon installations, and cyberpunk night market food stalls.'
  },
  {
    id: 'rooftop-blue',
    name: 'Rooftop Blue Trio',
    tag: 'JAZZ',
    date: 'Fri · 9:30 PM · Skyline Deck',
    price: '₹899',
    priceNum: 899,
    total_seats: 120,
    available_seats: 12,
    duration_minutes: 60,
    status: 'ACTIVE',
    image: '/assets/event-jazz-CCYVK6-g.jpg',
    description: 'Intimate evening jazz under the city skyline. Featuring classical saxophone, upright bass, and vintage piano arrangements.'
  },
  {
    id: 'late-laughs',
    name: 'Late Laughs Live',
    tag: 'COMEDY',
    date: 'Sun · 7:00 PM · The Basement',
    price: '₹649',
    priceNum: 649,
    total_seats: 240,
    available_seats: 67,
    duration_minutes: 45,
    status: 'ACTIVE',
    image: '/assets/event-comedy-Bb4-fimN.jpg',
    description: 'Unfiltered, high-energy stand-up comedy showcase featuring top touring comedians and surprise special guests.'
  }
];

export const INITIAL_BOOKINGS = [
  {
    id: 'BK-9021',
    eventId: 'neon-night',
    event_name: 'Neon Night Market',
    status: 'CONFIRMED',
    date: 'Saturday · 8:00 PM',
    venue: 'Warehouse 9, Mumbai',
    seats: 2,
    totalAmount: '₹2,998',
    ticketCode: 'FD-NEON-8842-X',
    createdAt: '2026-10-03T19:30:00.000Z'
  }
];

// Backend API Request with graceful fallback
export async function apiRequest(endpoint, options = {}) {
  try {
    const res = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {})
      }
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || data.message || `Request failed with status ${res.status}`);
    }
    return data;
  } catch (err) {
    console.warn(`Backend API unavailable at ${endpoint}, using client state:`, err.message);
    throw err;
  }
}

// Session Management
export function getSession() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem('fairdrop-session');
    if (raw) return JSON.parse(raw);
  } catch (e) {
    console.error('Session load error', e);
  }
  const defaultSession = {
    user: {
      id: 'usr_guest_892',
      name: 'Alex Rivera',
      email: 'alex.rivera@example.com',
      role: 'user'
    },
    token: 'tok_demo_fairdrop_9817'
  };
  localStorage.setItem('fairdrop-session', JSON.stringify(defaultSession));
  return defaultSession;
}

export function setSession(session) {
  if (typeof window === 'undefined') return;
  if (session) {
    localStorage.setItem('fairdrop-session', JSON.stringify(session));
  } else {
    localStorage.removeItem('fairdrop-session');
  }
  window.dispatchEvent(new Event('fairdrop-session-change'));
}

// Events Management
export function getEvents() {
  if (typeof window === 'undefined') return INITIAL_EVENTS;
  try {
    const raw = localStorage.getItem('fairdrop-events');
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  localStorage.setItem('fairdrop-events', JSON.stringify(INITIAL_EVENTS));
  return INITIAL_EVENTS;
}

export function saveEvents(events) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('fairdrop-events', JSON.stringify(events));
  window.dispatchEvent(new Event('fairdrop-events-change'));
}

// Bookings Management
export function getBookings() {
  if (typeof window === 'undefined') return INITIAL_BOOKINGS;
  try {
    const raw = localStorage.getItem('fairdrop-bookings');
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  localStorage.setItem('fairdrop-bookings', JSON.stringify(INITIAL_BOOKINGS));
  return INITIAL_BOOKINGS;
}

export function addBooking(booking) {
  const current = getBookings();
  const updated = [booking, ...current];
  localStorage.setItem('fairdrop-bookings', JSON.stringify(updated));
  window.dispatchEvent(new Event('fairdrop-bookings-change'));
  return updated;
}

// Real Cryptographic Proof-Of-Work solver using WebCrypto API
export async function solveProofOfWork(challenge = 'fairdrop-pow-seed', difficulty = 2, onProgress) {
  let nonce = 0;
  const targetPrefix = '0'.repeat(difficulty);
  const encoder = new TextEncoder();
  const startTime = Date.now();

  while (nonce < 5000000) {
    const data = encoder.encode(challenge + nonce);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

    if (hashHex.startsWith(targetPrefix)) {
      if (onProgress) onProgress({ nonce, hash: hashHex, elapsed: Date.now() - startTime });
      return { nonce, hash: hashHex, elapsed: Date.now() - startTime };
    }

    nonce++;
    if (nonce % 500 === 0) {
      if (onProgress) onProgress({ nonce, hash: hashHex, elapsed: Date.now() - startTime });
      await new Promise(r => setTimeout(r, 0));
    }
  }
  throw new Error('Proof of work timeout');
}
