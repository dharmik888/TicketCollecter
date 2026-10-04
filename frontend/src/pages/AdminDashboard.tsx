import React, { useEffect, useState } from 'react';
import { useAuthStore } from '../store/authStore';
import { useNavigate } from 'react-router-dom';

interface EventAdmin {
  id: string;
  name: string;
  total_seats: number;
  available_seats: number;
  status: string;
}

const maskEmail = (email: string) => {
  if (!email || !email.includes('@')) return 'N/A';
  const [name, domain] = email.split('@');
  return name.slice(0, 2) + '***@' + domain;
};

const maskPhone = (phone: string) => {
  if (!phone || phone.length < 7) return 'N/A';
  return phone.slice(0, 3) + '****' + phone.slice(-4);
};

const maskString = (str: string) => {
  if (!str) return 'N/A';
  return str.slice(0, 3) + '***';
};

export const AdminDashboard: React.FC = () => {
  const { user, token } = useAuthStore();
  const navigate = useNavigate();

  const [events, setEvents] = useState<EventAdmin[]>([]);
  const [name, setName] = useState('');
  const [seats, setSeats] = useState(100);
  const [duration, setDuration] = useState<number | ''>('');
  const [queueModal, setQueueModal] = useState<any[] | null>(null);

  const fetchEvents = () => {
    fetch('http://localhost:3001/api/events', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setEvents(data);
        } else {
          console.error("Expected array but got:", data);
          setEvents([]);
        }
      })
      .catch(err => {
        console.error(err);
        setEvents([]);
      });
  };

  useEffect(() => {
    if (user?.role === 'admin') {
      fetchEvents();
    }
  }, [user]);

  const handleCreate = async () => {
    await fetch('http://localhost:3001/api/events', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ 
        name, 
        total_seats: seats, 
        duration_minutes: duration === '' ? undefined : Number(duration) 
      })
    });
    fetchEvents();
  };

  const handleOpen = async (id: string) => {
    await fetch(`http://localhost:3001/api/events/${id}/open`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    });
    fetchEvents();
  };

  const handleStop = async (id: string) => {
    await fetch(`http://localhost:3001/api/events/${id}/stop`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    });
    fetchEvents();
  };

  const handleViewQueue = async (id: string) => {
    const res = await fetch(`http://localhost:3001/api/events/${id}/queue-details`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await res.json();
    if (Array.isArray(data)) {
      setQueueModal(data);
    } else {
      console.error("Expected queue data array but got:", data);
      setQueueModal([]);
    }
  };

  if (user?.role !== 'admin') {
    return (
      <div className="min-h-screen bg-slate-900 text-slate-100 p-8 flex flex-col items-center justify-center">
        <h1 className="text-4xl font-bold mb-4 text-red-500">403 Forbidden</h1>
        <p className="mb-8 text-slate-400">You do not have permission to view the Admin Dashboard.</p>
        <button onClick={() => navigate('/fairdrop-staff')} className="bg-red-600 hover:bg-red-700 px-6 py-3 rounded-lg font-bold">Go to Staff Login</button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-8">
      {queueModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl max-w-4xl w-full shadow-2xl max-h-[80vh] overflow-y-auto">
            <h2 className="text-2xl font-bold mb-6 text-white">Live Queue Details (Secure View)</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left bg-slate-800 rounded-xl overflow-hidden mb-6">
                <thead className="bg-slate-950 text-slate-400">
                  <tr>
                    <th className="px-4 py-2">Name</th>
                    <th className="px-4 py-2">Phone</th>
                    <th className="px-4 py-2">Email</th>
                    <th className="px-4 py-2">Address</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700">
                  {queueModal.map((qUser: any) => (
                    <tr key={qUser.userId}>
                      <td className="px-4 py-2 font-bold">{qUser.fullName || qUser.userId}</td>
                      <td className="px-4 py-2">{maskPhone(qUser.phoneNumber)}</td>
                      <td className="px-4 py-2">{maskEmail(qUser.emailId)}</td>
                      <td className="px-4 py-2 truncate max-w-xs">{maskString(qUser.address)}</td>
                    </tr>
                  ))}
                  {queueModal.length === 0 && (
                    <tr><td colSpan={4} className="px-4 py-4 text-center text-slate-400">Queue is currently empty.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <button onClick={() => setQueueModal(null)} className="bg-slate-700 hover:bg-slate-600 px-6 py-2 rounded-lg font-bold">Close</button>
          </div>
        </div>
      )}

      <h1 className="text-3xl font-bold mb-8">Admin Dashboard</h1>
      
      <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 mb-8 max-w-3xl">
        <h2 className="text-xl font-bold mb-4">Create Drop Event</h2>
        <div className="flex gap-4">
          <input 
            className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2"
            placeholder="Event Name" 
            value={name} onChange={e => setName(e.target.value)} 
          />
          <input 
            className="w-32 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2"
            type="number"
            placeholder="Seats"
            value={seats} onChange={e => setSeats(Number(e.target.value))} 
          />
          <input 
            className="w-48 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2"
            type="number"
            placeholder="Duration (mins)"
            value={duration} onChange={e => setDuration(e.target.value === '' ? '' : Number(e.target.value))} 
          />
          <button 
            onClick={handleCreate}
            className="bg-indigo-600 hover:bg-indigo-700 px-6 rounded-lg font-bold transition-colors"
          >
            Create
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left bg-slate-800 rounded-xl overflow-hidden">
          <thead className="bg-slate-950 text-slate-400">
            <tr>
              <th className="px-6 py-4">ID</th>
              <th className="px-6 py-4">Name</th>
              <th className="px-6 py-4">Capacity</th>
              <th className="px-6 py-4">Available</th>
              <th className="px-6 py-4">Status</th>
              <th className="px-6 py-4">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700">
            {(Array.isArray(events) ? events : []).map(event => (
              <tr key={event.id}>
                <td className="px-6 py-4 font-mono text-xs">{event.id}</td>
                <td className="px-6 py-4 font-bold">{event.name}</td>
                <td className="px-6 py-4">{event.total_seats}</td>
                <td className="px-6 py-4">{event.available_seats}</td>
                <td className="px-6 py-4">
                  <span className={`px-2 py-1 rounded text-xs font-bold ${event.status === 'ACTIVE' ? 'bg-green-500/20 text-green-400' : 'bg-slate-700'}`}>
                    {event.status}
                  </span>
                </td>
                <td className="px-6 py-4 flex gap-2 flex-wrap">
                  {event.status === 'PENDING' && (
                    <button 
                      onClick={() => handleOpen(event.id)}
                      className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded font-bold text-sm"
                    >
                      Open Queue
                    </button>
                  )}
                  {event.status === 'ACTIVE' && (
                    <button 
                      onClick={() => handleStop(event.id)}
                      className="bg-red-600 hover:bg-red-700 px-4 py-2 rounded font-bold text-sm"
                    >
                      Stop Sales
                    </button>
                  )}
                  <button 
                    onClick={() => handleViewQueue(event.id)}
                    className="bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded font-bold text-sm"
                  >
                    View Queue
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
