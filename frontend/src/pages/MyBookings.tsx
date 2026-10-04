import React, { useEffect, useState } from 'react';
import { useAuthStore } from '../store/authStore';
import { useNavigate } from 'react-router-dom';

export const MyBookings: React.FC = () => {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const [bookings, setBookings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user) {
      fetch('http://localhost:3001/api/events/user/bookings', {
        headers: { 'user-id': user.id }
      })
      .then(r => r.json())
      .then(data => {
        setBookings(data);
        setLoading(false);
      });
    }
  }, [user]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-8 pt-20">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-10">
          <div>
            <h1 className="text-4xl font-extrabold bg-gradient-to-r from-indigo-500 to-purple-500 text-transparent bg-clip-text">My Bookings</h1>
            <p className="text-slate-400 mt-2">Manage your secured tickets</p>
          </div>
          <button onClick={() => navigate('/')} className="bg-slate-800 hover:bg-slate-700 px-6 py-3 rounded-xl font-bold transition-colors">Back to Home</button>
        </div>
        
        {loading ? (
          <p className="text-slate-500 text-center">Loading your tickets...</p>
        ) : (
          <div className="grid gap-4">
            {bookings.map(b => (
              <div key={b.id} className="bg-slate-900 border border-slate-800 p-6 rounded-2xl flex flex-col md:flex-row justify-between items-start md:items-center shadow-lg hover:border-slate-700 transition-colors">
                <div className="mb-4 md:mb-0">
                  <h3 className="text-2xl font-bold mb-1 text-white">{b.eventName}</h3>
                  <div className="flex items-center gap-4 mt-2">
                    <p className="text-sm font-mono text-slate-500 bg-slate-950 px-3 py-1 rounded-md">ID: {b.id}</p>
                    <p className="text-sm text-slate-400">Qty: 1</p>
                  </div>
                </div>
                <span className={`px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider ${b.status === 'CONFIRMED' ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'}`}>
                  {b.status}
                </span>
              </div>
            ))}
            {bookings.length === 0 && (
              <div className="bg-slate-900 border border-slate-800 p-12 rounded-2xl text-center shadow-lg">
                <p className="text-slate-400 mb-4 text-lg">You have no active bookings.</p>
                <button onClick={() => navigate('/')} className="text-purple-400 hover:text-purple-300 font-bold underline underline-offset-4">Browse Upcoming Drops</button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
