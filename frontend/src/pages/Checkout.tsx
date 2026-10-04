import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export const Checkout: React.FC = () => {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [cc, setCc] = useState('');
  const [paypalEmail, setPaypalEmail] = useState('');
  const [bankAccount, setBankAccount] = useState('');
  const [appleId, setAppleId] = useState('');
  const [paymentMethod, setPaymentMethod] = useState<'card' | 'paypal' | 'online' | 'apple'>('card');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleCheckout = async () => {
    setLoading(true);
    // simulate payment delay
    await new Promise(r => setTimeout(r, 1500));
    
    let paymentAccountId = '';
    if (paymentMethod === 'card') paymentAccountId = cc;
    if (paymentMethod === 'paypal') paymentAccountId = paypalEmail;
    if (paymentMethod === 'online') paymentAccountId = bankAccount;
    if (paymentMethod === 'apple') paymentAccountId = appleId;

    if (!paymentAccountId) {
      alert('Please enter your payment details.');
      setLoading(false);
      return;
    }

    const res = await fetch(`http://localhost:3001/api/events/${eventId}/checkout`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'user-id': user?.id || '' 
      },
      body: JSON.stringify({ paymentAccountId })
    });
    
    if (res.ok) {
      setSuccess(true);
    } else {
      const data = await res.json();
      alert(data.error || 'Checkout failed!');
    }
    setLoading(false);
  };

  if (success) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4 text-slate-100">
        <div className="bg-green-500/10 text-green-400 p-10 rounded-2xl max-w-md text-center border border-green-500/30 shadow-2xl">
          <div className="bg-green-500/20 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
          </div>
          <h2 className="text-3xl font-bold mb-4">Payment Successful!</h2>
          <p className="mb-8 text-green-200/70">Your ticket has been confirmed. The digital ticket receipt has been sent to your email.</p>
          <button 
            onClick={() => navigate('/bookings')} 
            className="bg-green-600 text-white hover:bg-green-500 py-3 px-6 rounded-xl font-bold w-full transition-all shadow-lg hover:shadow-green-500/25"
          >
            View My Bookings
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl w-full max-w-md shadow-2xl">
        <h2 className="text-2xl font-bold mb-2 text-white">Complete Purchase</h2>
        <p className="text-slate-400 mb-8">You have 5 minutes to complete your payment or your reservation will be released.</p>
        
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2 scrollbar-hide">
          {['card', 'paypal', 'online', 'apple'].map(m => (
            <button 
              key={m}
              onClick={() => setPaymentMethod(m as any)}
              className={`px-4 py-2 rounded-lg font-bold capitalize transition-colors whitespace-nowrap ${paymentMethod === m ? 'bg-purple-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`}
            >
              {m === 'card' ? 'Credit Card' : m === 'online' ? 'Online Banking' : m === 'apple' ? 'Apple Pay' : m}
            </button>
          ))}
        </div>

        {paymentMethod === 'card' && (
          <div className="mb-8 animate-in fade-in slide-in-from-bottom-2">
            <label className="block text-sm font-bold text-slate-400 mb-2">Credit Card Number</label>
            <input 
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-4 focus:outline-none focus:ring-2 focus:ring-purple-500 text-white font-mono tracking-widest text-lg"
              placeholder="0000 0000 0000 0000" 
              value={cc} onChange={e => setCc(e.target.value)}
            />
          </div>
        )}

        {paymentMethod === 'paypal' && (
          <div className="mb-8 p-6 bg-[#00457C]/10 border border-[#00457C] rounded-xl text-center animate-in fade-in slide-in-from-bottom-2">
            <h3 className="text-xl font-bold text-[#0079C1] mb-4">PayPal Checkout</h3>
            <input 
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-[#0079C1] text-white"
              placeholder="PayPal Email Address" 
              type="email"
              value={paypalEmail} onChange={e => setPaypalEmail(e.target.value)}
            />
          </div>
        )}

        {paymentMethod === 'online' && (
          <div className="mb-8 p-6 bg-teal-500/10 border border-teal-500/50 rounded-xl text-center animate-in fade-in slide-in-from-bottom-2">
            <h3 className="text-xl font-bold text-teal-400 mb-4">Online Banking</h3>
            <input 
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-teal-500 text-white font-mono"
              placeholder="Bank Account Number / Routing" 
              value={bankAccount} onChange={e => setBankAccount(e.target.value)}
            />
          </div>
        )}

        {paymentMethod === 'apple' && (
          <div className="mb-8 p-6 bg-slate-800 border border-slate-700 rounded-xl text-center animate-in fade-in slide-in-from-bottom-2">
            <h3 className="text-xl font-bold text-white mb-4">Apple Pay</h3>
            <input 
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-white text-white"
              placeholder="Apple ID Email (for verification)" 
              type="email"
              value={appleId} onChange={e => setAppleId(e.target.value)}
            />
          </div>
        )}
        
        <button 
          onClick={handleCheckout}
          disabled={loading || (paymentMethod === 'card' && cc.length < 16) || (paymentMethod === 'paypal' && !paypalEmail) || (paymentMethod === 'online' && !bankAccount) || (paymentMethod === 'apple' && !appleId)}
          className="w-full bg-purple-600 hover:bg-purple-700 py-4 rounded-xl font-bold text-lg transition-all shadow-lg hover:shadow-purple-500/25 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Processing Securely...' : paymentMethod === 'card' ? 'Pay $99.00' : `Checkout with ${paymentMethod === 'apple' ? 'Apple Pay' : paymentMethod === 'online' ? 'Bank' : 'PayPal'}`}
        </button>
      </div>
    </div>
  );
};
