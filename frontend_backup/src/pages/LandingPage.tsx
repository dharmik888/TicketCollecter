import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useEventStore } from '../store/eventStore';

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const { login, logout, user } = useAuthStore();
  const { events, setEvents } = useEventStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  // Registration Modal State
  const [selectedEventForDetails, setSelectedEventForDetails] = useState<string | null>(null);
  const [fullName, setFullName] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [emailId, setEmailId] = useState('');
  const [address, setAddress] = useState('');

  const [isLoginMode, setIsLoginMode] = useState(true);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  useEffect(() => {
    fetch('http://localhost:3001/api/events')
      .then(res => res.json())
      .then(data => setEvents(data));
  }, [setEvents]);

  const handleAuth = async (isLogin: boolean) => {
    const endpoint = isLogin ? '/login' : '/register';
    const res = await fetch(`http://localhost:3001/api/auth${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (res.ok) {
      if (isLogin) {
        login(data.token, data.user);
      } else {
        alert('Account created successfully! Please log in.');
        setIsLoginMode(true);
      }
    } else {
      alert(data.error);
    }
  };

  const handleRegisterDetails = async () => {
    if (!selectedEventForDetails || !user) return;
    try {
      const res = await fetch(`http://localhost:3001/api/events/${selectedEventForDetails}/register-details`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'user-id': user.id },
        body: JSON.stringify({ fullName, phoneNumber, emailId, address })
      });
      const data = await res.json();
      if (res.ok) {
        navigate(`/queue/${selectedEventForDetails}`);
      } else {
        alert(data.error);
        setSelectedEventForDetails(null);
      }
    } catch (e: any) {
      alert("An error occurred connecting to the server.");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center py-20 px-4">
      <h1 className="text-5xl font-extrabold mb-2 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 text-transparent bg-clip-text">
        Fair Drop
      </h1>
      <p className="text-slate-400 mb-12">The un-bottable high demand drop platform.</p>

      {selectedEventForDetails && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl max-w-md w-full shadow-2xl">
            <h2 className="text-2xl font-bold mb-2 text-white">Registration Details</h2>
            <p className="text-slate-400 mb-6">Please provide your details to enter the waiting room.</p>
            
            <input 
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 mb-4 focus:outline-none focus:ring-2 focus:ring-purple-500 text-white"
              placeholder="Full Government Name" 
              value={fullName} onChange={e => setFullName(e.target.value)} 
            />
            <input 
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 mb-4 focus:outline-none focus:ring-2 focus:ring-purple-500 text-white"
              placeholder="Phone Number" 
              value={phoneNumber} onChange={e => setPhoneNumber(e.target.value)} 
            />
            <input 
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 mb-4 focus:outline-none focus:ring-2 focus:ring-purple-500 text-white"
              placeholder="Email ID" 
              type="email"
              value={emailId} onChange={e => setEmailId(e.target.value)} 
            />
            <textarea 
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 mb-6 focus:outline-none focus:ring-2 focus:ring-purple-500 text-white min-h-[80px]"
              placeholder="Address of Current Residence" 
              value={address} onChange={e => setAddress(e.target.value)} 
            />
            
            <div className="flex gap-4">
              <button 
                onClick={() => setSelectedEventForDetails(null)}
                className="flex-1 bg-slate-700 hover:bg-slate-600 py-3 rounded-lg font-semibold transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={handleRegisterDetails}
                disabled={!fullName || !phoneNumber || !emailId || !address}
                className="flex-1 bg-purple-600 hover:bg-purple-700 py-3 rounded-lg font-semibold transition-colors disabled:opacity-50"
              >
                Confirm & Join Queue
              </button>
            </div>
          </div>
        </div>
      )}

      {!user ? (
        <div className="bg-slate-900 p-8 rounded-2xl border border-slate-800 shadow-2xl w-full max-w-md">
          <h2 className="text-2xl font-bold mb-6">{isLoginMode ? 'Login to Fair Drop' : 'Create an Account'}</h2>
          
          <input 
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 mb-4 focus:outline-none focus:ring-2 focus:ring-purple-500"
            placeholder="Email Address" 
            value={email} onChange={e => setEmail(e.target.value)} 
          />
          <input 
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 mb-6 focus:outline-none focus:ring-2 focus:ring-purple-500"
            placeholder="Password" 
            type="password"
            value={password} onChange={e => setPassword(e.target.value)} 
          />

          <button 
            onClick={() => handleAuth(isLoginMode)}
            className="w-full bg-purple-600 hover:bg-purple-700 py-3 rounded-lg font-semibold transition-colors mb-6 shadow-lg shadow-purple-600/30"
          >
            {isLoginMode ? 'Secure Login' : 'Sign Up Now'}
          </button>

          <p className="text-center text-slate-400 text-sm">
            {isLoginMode ? "Don't have an account? " : "Already have an account? "}
            <button 
              onClick={() => setIsLoginMode(!isLoginMode)}
              className="text-purple-400 hover:text-purple-300 font-bold underline underline-offset-2"
            >
              {isLoginMode ? 'Sign up' : 'Login'}
            </button>
          </p>
        </div>
      ) : (
        <div className="w-full max-w-4xl">
          <div className="flex justify-between items-center mb-8">
            <h2 className="text-2xl font-bold">Upcoming Drops</h2>
            <div className="flex items-center gap-4 relative">
              <span className="text-slate-400 hidden sm:inline-block">Logged in as {user.email || 'User'}</span>
              
              <div className="relative">
                <button 
                  onClick={() => setIsProfileOpen(!isProfileOpen)}
                  className="w-10 h-10 rounded-full bg-purple-600 hover:bg-purple-500 text-white font-bold flex items-center justify-center transition-colors shadow-lg shadow-purple-600/20"
                >
                  {user.email ? user.email.charAt(0).toUpperCase() : 'U'}
                </button>

                {isProfileOpen && (
                  <div className="absolute right-0 mt-2 w-48 bg-slate-800 border border-slate-700 rounded-xl shadow-2xl py-2 z-50">
                    <button 
                      onClick={() => { setIsProfileOpen(false); navigate('/'); }}
                      className="w-full text-left px-4 py-2 hover:bg-slate-700 text-slate-200 transition-colors"
                    >
                      Browse Events
                    </button>
                    <button 
                      onClick={() => { setIsProfileOpen(false); navigate('/bookings'); }}
                      className="w-full text-left px-4 py-2 hover:bg-slate-700 text-slate-200 transition-colors"
                    >
                      My Bookings
                    </button>
                    <div className="border-t border-slate-700 my-1"></div>
                    <button 
                      onClick={() => { setIsProfileOpen(false); logout(); }}
                      className="w-full text-left px-4 py-2 hover:bg-slate-700 text-red-400 transition-colors"
                    >
                      Logout
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {events.map(event => (
              <div key={event.id} className="bg-slate-900 border border-slate-800 p-6 rounded-2xl flex flex-col items-start shadow-xl hover:border-purple-500/50 transition-colors">
                <div className="flex justify-between w-full mb-4">
                  <h3 className="text-xl font-bold text-white">{event.name}</h3>
                  <span className={`px-3 py-1 rounded-full text-xs font-bold ${event.status === 'ACTIVE' ? 'bg-green-500/20 text-green-400' : 'bg-slate-700 text-slate-300'}`}>
                    {event.status}
                  </span>
                </div>
                <p className="text-slate-400 mb-6">Total Seats: {event.total_seats}</p>
                <button 
                  disabled={event.status !== 'ACTIVE'}
                  onClick={() => setSelectedEventForDetails(event.id)}
                  className="w-full py-3 rounded-xl font-bold transition-all disabled:opacity-50 disabled:cursor-not-allowed bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 shadow-lg hover:shadow-purple-500/25"
                >
                  {event.status === 'ACTIVE' ? 'Enter Waiting Room' : 'Not Yet Open'}
                </button>
              </div>
            ))}
            {events.length === 0 && <p className="text-slate-500">No events currently scheduled.</p>}
          </div>
        </div>
      )}
    </div>
  );
};
