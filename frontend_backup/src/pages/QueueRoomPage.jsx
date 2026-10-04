import React, { useState, useEffect, useRef } from 'react';
import { ShieldCheck, ArrowRight, RefreshCw, CheckCircle2, Clock, Activity, Cpu } from 'lucide-react';
import { getEvents, solveProofOfWork } from '../data/mockData';

export function QueueRoomPage({ eventId, onNavigate }) {
  const events = getEvents();
  const event = events.find((e) => e.id === eventId) || events[0];

  const [stage, setStage] = useState('pow'); // 'pow' | 'queued' | 'ready'
  const [statusText, setStatusText] = useState('Validating browser environment...');
  const [position, setPosition] = useState(12);
  const [progress, setProgress] = useState(15);
  const [estWait, setEstWait] = useState('01:30');
  const [powNonce, setPowNonce] = useState(null);
  const [powHash, setPowHash] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const timerRef = useRef(null);

  useEffect(() => {
    let isCancelled = false;

    async function runVerificationAndQueue() {
      try {
        setStatusText('Solving client-side proof-of-work challenge...');
        const result = await solveProofOfWork(`fairdrop-seed-${event.id}-${Date.now()}`, 2, (p) => {
          if (!isCancelled) {
            setPowNonce(p.nonce);
            setPowHash(p.hash);
          }
        });

        if (isCancelled) return;
        setPowNonce(result.nonce);
        setPowHash(result.hash);

        setStatusText('Connecting to fair FIFO allocation engine...');
        await new Promise((r) => setTimeout(r, 600));
        if (isCancelled) return;

        setStatusText('Queue spot confirmed. Maintaining persistent session.');
        setStage('queued');
        setPosition(8);
        setProgress(35);
        setEstWait('01:05');

        let currentPos = 8;
        timerRef.current = setInterval(() => {
          currentPos -= 1;
          if (currentPos <= 1) {
            clearInterval(timerRef.current);
            setPosition(1);
            setProgress(100);
            setEstWait('00:00');
            setStatusText('Your tickets are ready for reservation!');
            setStage('ready');

            setTimeout(() => {
              if (!isCancelled) {
                onNavigate(`/checkout/${event.id}`);
              }
            }, 1600);
          } else {
            setPosition(currentPos);
            setProgress(Math.round(((8 - currentPos + 1) / 8) * 90));
            const secLeft = currentPos * 8;
            const mins = String(Math.floor(secLeft / 60)).padStart(2, '0');
            const secs = String(secLeft % 60).padStart(2, '0');
            setEstWait(`${mins}:${secs}`);
          }
        }, 1400);
      } catch (err) {
        if (!isCancelled) {
          setErrorMessage(err.message || 'Verification challenge failed.');
        }
      }
    }

    runVerificationAndQueue();

    return () => {
      isCancelled = true;
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [event.id]);

  return (
    <main style={{ minHeight: 'calc(100vh - 64px)', backgroundColor: 'var(--bg-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 24px' }}>
      <div className="card" style={{ width: '100%', maxWidth: '640px', padding: '36px' }}>
        {/* Header Badge & Title */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', paddingBottom: '20px', borderBottom: '1px solid var(--border-color)' }}>
          <div>
            <span className="badge badge-blue">{event.name}</span>
            <h1 style={{ fontSize: '22px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '6px' }}>
              Fair Queue Room
            </h1>
          </div>
          <div className="badge badge-green">
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--success)' }} className="pulse-clean" />
            Live Session Active
          </div>
        </div>

        {/* Center Queue Status */}
        <div style={{ textAlign: 'center', padding: '36px 0 28px 0' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Current Queue Position
          </div>

          <div style={{ fontSize: '72px', fontWeight: 700, color: stage === 'ready' ? 'var(--success)' : 'var(--accent-primary)', letterSpacing: '-0.03em', lineHeight: 1.1, marginTop: '8px' }}>
            {stage === 'ready' ? '1' : position !== null ? position : '—'}
          </div>

          <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '8px' }}>
            {stage === 'ready'
              ? 'You have reached the front of the queue! Redirecting to checkout...'
              : 'Hold tight while fans ahead of you complete their reservation.'}
          </p>

          {/* Verification hash note */}
          {powHash && (
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', marginTop: '12px', padding: '4px 10px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-secondary)', fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
              <Cpu size={12} style={{ color: 'var(--accent-primary)' }} />
              SHA-256 Verified · Nonce #{powNonce}
            </div>
          )}
        </div>

        {/* Queue Progress Bar */}
        <div style={{ width: '100%', height: '6px', backgroundColor: 'var(--bg-secondary)', borderRadius: '3px', overflow: 'hidden' }}>
          <div
            style={{
              width: `${progress}%`,
              height: '100%',
              backgroundColor: stage === 'ready' ? 'var(--success)' : 'var(--accent-primary)',
              borderRadius: '3px',
              transition: 'width 0.4s ease'
            }}
          />
        </div>

        {/* Stats Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: '24px' }}>
          <div style={{ padding: '14px', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', textAlign: 'center' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 500 }}>
              Estimated Wait
            </div>
            <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
              <Clock size={16} style={{ color: 'var(--accent-primary)' }} />
              {estWait}
            </div>
          </div>

          <div style={{ padding: '14px', backgroundColor: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', textAlign: 'center' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 500 }}>
              Queue Status
            </div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--success)', marginTop: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
              <ShieldCheck size={16} />
              Session Verified
            </div>
          </div>
        </div>

        {/* Stage Ready Callout Button */}
        {stage === 'ready' && (
          <div style={{ marginTop: '24px' }}>
            <button
              onClick={() => onNavigate(`/checkout/${event.id}`)}
              className="btn btn-primary btn-lg"
              style={{ width: '100%', backgroundColor: 'var(--success)', borderColor: 'var(--success)' }}
            >
              Proceed to Secure Checkout <ArrowRight size={16} />
            </button>
          </div>
        )}

        {/* Error Alert if any */}
        {errorMessage && (
          <div style={{ marginTop: '20px', padding: '12px 16px', backgroundColor: 'var(--error-bg)', color: 'var(--error)', borderRadius: 'var(--radius-md)', fontSize: '13px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>{errorMessage}</span>
            <button
              onClick={() => window.location.reload()}
              className="btn btn-secondary btn-sm"
            >
              <RefreshCw size={12} /> Retry
            </button>
          </div>
        )}

        {/* Reassurance Footer */}
        <div style={{ marginTop: '28px', paddingTop: '16px', borderTop: '1px solid var(--border-color)', fontSize: '12px', color: 'var(--text-secondary)', textAlign: 'center', lineHeight: 1.5 }}>
          Please keep this browser window open. Refreshing will retain your position, but leaving may expire your verification token.
        </div>
      </div>
    </main>
  );
}
