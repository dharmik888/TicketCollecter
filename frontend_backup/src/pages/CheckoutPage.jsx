import React, { useState, useEffect } from 'react';
import { CreditCard, Smartphone, Landmark, ShieldCheck, Clock, ArrowLeft, CheckCircle2, Lock } from 'lucide-react';
import { getEvents, getSession, addBooking } from '../data/mockData';

export function CheckoutPage({ eventId, onNavigate }) {
  const events = getEvents();
  const event = events.find((e) => e.id === eventId) || events[0];
  const session = getSession();

  const regData = JSON.parse(
    sessionStorage.getItem(`fairdrop_registration_${event.id}`) || '{"seatCount": 1, "name": "Alex Rivera", "email": "alex.rivera@example.com"}'
  );
  const seats = regData.seatCount || 1;
  const subtotal = event.priceNum * seats;
  const bookingFee = 49;
  const total = subtotal + bookingFee;

  const [paymentMethod, setPaymentMethod] = useState('card');
  const [cardNumber, setCardNumber] = useState('4532 8920 1192 8841');
  const [cardExpiry, setCardExpiry] = useState('12/28');
  const [cardCvv, setCardCvv] = useState('482');
  const [upiId, setUpiId] = useState('alex@oksbi');
  const [bankName, setBankName] = useState('HDFC Bank');
  const [isProcessing, setIsProcessing] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(600); // 10 minutes

  useEffect(() => {
    const interval = setInterval(() => {
      setSecondsLeft((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const formatTimer = (s) => {
    const mins = String(Math.floor(s / 60)).padStart(2, '0');
    const secs = String(s % 60).padStart(2, '0');
    return `${mins}:${secs}`;
  };

  const handlePay = (e) => {
    e.preventDefault();
    setIsProcessing(true);

    setTimeout(() => {
      const newBooking = {
        id: `BK-${Math.floor(1000 + Math.random() * 9000)}`,
        eventId: event.id,
        event_name: event.name,
        status: 'CONFIRMED',
        date: event.date,
        venue: event.date.split('·')[2]?.trim() || 'Main Venue, Mumbai',
        seats: seats,
        totalAmount: `₹${total.toLocaleString('en-IN')}`,
        ticketCode: `FD-${event.id.toUpperCase().slice(0, 4)}-${Math.floor(1000 + Math.random() * 9000)}-OK`,
        createdAt: new Date().toISOString(),
        attendeeName: regData.name || session?.user?.name || 'Alex Rivera',
        attendeeEmail: regData.email || session?.user?.email || 'alex@example.com'
      };

      addBooking(newBooking);
      setIsProcessing(false);
      onNavigate('/bookings');
    }, 800);
  };

  return (
    <main style={{ maxWidth: '1100px', margin: '0 auto', padding: '36px 24px 64px 24px' }}>
      <button
        onClick={() => onNavigate('/')}
        className="btn btn-secondary btn-sm"
        style={{ marginBottom: '20px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
      >
        <ArrowLeft size={14} /> Cancel & Return to Events
      </button>

      {/* 10-Minute Reservation Hold Alert */}
      <div style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '14px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', marginBottom: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--success)' }} className="pulse-clean" />
          <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
            Your selected seats are temporarily reserved
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: 'var(--text-secondary)' }}>
          <Clock size={15} style={{ color: 'var(--accent-primary)' }} />
          <span>Hold expires in:</span>
          <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'monospace', fontSize: '14px' }}>
            {formatTimer(secondsLeft)}
          </span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '32px', alignItems: 'start' }}>
        {/* Left Column: Payment Details */}
        <div>
          <div className="card" style={{ padding: '28px' }}>
            <h1 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-primary)' }}>
              Payment Method
            </h1>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
              All transactions are encrypted with 256-bit SSL security.
            </p>

            {/* Payment Method Selector Tabs */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', marginTop: '20px' }}>
              <button
                type="button"
                onClick={() => setPaymentMethod('card')}
                className={`btn ${paymentMethod === 'card' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                style={{ justifyContent: 'center', padding: '10px' }}
              >
                <CreditCard size={15} /> Card
              </button>

              <button
                type="button"
                onClick={() => setPaymentMethod('upi')}
                className={`btn ${paymentMethod === 'upi' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                style={{ justifyContent: 'center', padding: '10px' }}
              >
                <Smartphone size={15} /> UPI
              </button>

              <button
                type="button"
                onClick={() => setPaymentMethod('bank')}
                className={`btn ${paymentMethod === 'bank' ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                style={{ justifyContent: 'center', padding: '10px' }}
              >
                <Landmark size={15} /> Net Banking
              </button>
            </div>

            <form onSubmit={handlePay} style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {paymentMethod === 'card' && (
                <>
                  <div>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '6px' }}>
                      Card Number
                    </label>
                    <input
                      type="text"
                      required
                      value={cardNumber}
                      onChange={(e) => setCardNumber(e.target.value)}
                      style={{ fontFamily: 'monospace' }}
                    />
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '6px' }}>
                        Expiration Date
                      </label>
                      <input
                        type="text"
                        required
                        value={cardExpiry}
                        onChange={(e) => setCardExpiry(e.target.value)}
                        placeholder="MM/YY"
                        style={{ fontFamily: 'monospace' }}
                      />
                    </div>

                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '6px' }}>
                        Security Code (CVV)
                      </label>
                      <input
                        type="password"
                        required
                        maxLength={4}
                        value={cardCvv}
                        onChange={(e) => setCardCvv(e.target.value)}
                        placeholder="•••"
                        style={{ fontFamily: 'monospace' }}
                      />
                    </div>
                  </div>
                </>
              )}

              {paymentMethod === 'upi' && (
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '6px' }}>
                    UPI ID / Virtual Payment Address (VPA)
                  </label>
                  <input
                    type="text"
                    required
                    value={upiId}
                    onChange={(e) => setUpiId(e.target.value)}
                    placeholder="name@okhdfcbank"
                  />
                  <span style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px', display: 'block' }}>
                    A payment request will be sent to your UPI application.
                  </span>
                </div>
              )}

              {paymentMethod === 'bank' && (
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)', marginBottom: '6px' }}>
                    Select Bank
                  </label>
                  <select
                    value={bankName}
                    onChange={(e) => setBankName(e.target.value)}
                    style={{ cursor: 'pointer' }}
                  >
                    <option value="HDFC Bank">HDFC Bank</option>
                    <option value="State Bank of India">State Bank of India</option>
                    <option value="ICICI Bank">ICICI Bank</option>
                    <option value="Axis Bank">Axis Bank</option>
                    <option value="Kotak Mahindra Bank">Kotak Mahindra Bank</option>
                  </select>
                </div>
              )}

              <div style={{ paddingTop: '12px' }}>
                <button
                  type="submit"
                  disabled={isProcessing}
                  className="btn btn-primary btn-lg"
                  style={{ width: '100%' }}
                >
                  {isProcessing ? (
                    <>
                      <span className="spin-clean" style={{ display: 'inline-block', width: '14px', height: '14px', border: '2px solid #FFFFFF', borderTopColor: 'transparent', borderRadius: '50%' }} />
                      Authorizing Payment...
                    </>
                  ) : (
                    <>
                      <Lock size={15} /> Confirm & Pay ₹{total.toLocaleString('en-IN')}
                    </>
                  )}
                </button>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                <ShieldCheck size={14} style={{ color: 'var(--success)' }} />
                <span>Instant e-Ticket generation & confirmation</span>
              </div>
            </form>
          </div>
        </div>

        {/* Right Column: Order Summary */}
        <div>
          <div className="card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', paddingBottom: '12px', borderBottom: '1px solid var(--border-color)' }}>
              Order Summary
            </h2>

            <div style={{ marginTop: '16px' }}>
              <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                {event.name}
              </div>
              <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                {event.date}
              </div>
            </div>

            <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>{seats} × Admission Ticket</span>
                <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>₹{subtotal.toLocaleString('en-IN')}</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Fair Allocation & Security Fee</span>
                <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>₹{bookingFee}</span>
              </div>
            </div>

            <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Total Due</span>
              <span style={{ fontSize: '20px', fontWeight: 700, color: 'var(--accent-primary)' }}>
                ₹{total.toLocaleString('en-IN')}
              </span>
            </div>

            <div style={{ marginTop: '20px', padding: '12px', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              Tickets will be added to your <strong>My Bookings</strong> dashboard immediately upon transaction approval.
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
