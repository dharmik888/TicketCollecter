import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { io, Socket } from 'socket.io-client';
import { motion } from 'framer-motion';
import { useAuthStore } from '../store/authStore';
import { solvePoW } from '../utils/pow';

export const WaitingRoom: React.FC = () => {
  const { eventId } = useParams();
  const navigate = useNavigate();
  const { token, user } = useAuthStore();
  
  const [status, setStatus] = useState<'verifying' | 'queueing' | 'allocated' | 'sold_out' | 'already_allocated'>('verifying');
  const [powProgress, setPowProgress] = useState(0);
  const [position, setPosition] = useState<number | null>(null);
  
  const socketRef = useRef<Socket | null>(null);

  // Behavioral Data
  const behaviorRef = useRef({
    mouse_movements: 0,
    keystrokes: 0,
    scroll_events: 0,
    session_start: Date.now()
  });

  useEffect(() => {
    if (!token) {
      navigate('/');
      return;
    }

    const runPoW = async () => {
      try {
        // 1. Fetch Challenge
        const res = await fetch('http://localhost:3001/api/allocation/challenge', {
          headers: { 'user-id': user!.id }
        });
        const { challenge, difficulty } = await res.json();

        // 2. Solve Challenge
        const nonce = await solvePoW(challenge, difficulty, (curr) => {
          setPowProgress(curr);
        });

        // 3. Verify Challenge
        const verifyRes = await fetch('http://localhost:3001/api/allocation/verify-pow', {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'user-id': user!.id
          },
          body: JSON.stringify({ nonce })
        });

        if (verifyRes.ok) {
          connectToQueue();
        } else {
          alert("PoW Verification Failed. Are you a bot?");
        }
      } catch (e) {
        console.error(e);
      }
    };

    runPoW();

    // Track Behavior
    const onMouseMove = () => behaviorRef.current.mouse_movements++;
    const onKeyDown = () => behaviorRef.current.keystrokes++;
    const onScroll = () => behaviorRef.current.scroll_events++;
    
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('scroll', onScroll);

    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('scroll', onScroll);
      socketRef.current?.disconnect();
    };
  }, []);

  const connectToQueue = () => {
    setStatus('queueing');
    
    const socket = io('http://localhost:3001', {
      auth: { token }
    });
    socketRef.current = socket;

    socket.on('connect', () => {
      // Join the actual event queue
      socket.emit('join_queue', { eventId });
    });

    socket.on('queue_update', (data: { eventId: string, position: number }) => {
      if (data.eventId === eventId) {
        setPosition(data.position);
      }
    });

    socket.on('allocation_result', (data: { eventId: string, status: string }) => {
      if (data.eventId === eventId) {
        if (data.status === 'success') {
          setStatus('allocated');
          setTimeout(() => navigate(`/checkout/${eventId}`), 2000);
        }
        else if (data.status === 'sold_out') setStatus('sold_out');
        else if (data.status === 'already_allocated') setStatus('already_allocated');
      }
    });

    socket.on('bot_detected', (data: { message: string }) => {
      alert(data.message);
      navigate('/');
    });

    // Send behavior data periodically
    const behaviorInterval = setInterval(() => {
      socket.emit('behavior_data', {
        ...behaviorRef.current,
        session_duration_ms: Date.now() - behaviorRef.current.session_start
      });
      // Reset some stats
      behaviorRef.current.mouse_movements = 0;
      behaviorRef.current.keystrokes = 0;
      behaviorRef.current.scroll_events = 0;
    }, 5000);

    return () => clearInterval(behaviorInterval);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4">
      {status === 'verifying' && (
        <div className="flex flex-col items-center max-w-md w-full text-center">
          <h2 className="text-2xl font-bold mb-4">Verifying your browser...</h2>
          <p className="text-slate-400 mb-8">We are running a quick cryptographic puzzle to ensure you are a human. Please do not close this window.</p>
          <div className="w-full bg-slate-800 rounded-full h-3 mb-2 overflow-hidden">
            <motion.div 
              className="bg-purple-500 h-3"
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(100, (powProgress / 50000) * 100)}%` }}
            />
          </div>
          <span className="text-xs text-slate-500 font-mono">N: {powProgress}</span>
        </div>
      )}

      {status === 'queueing' && (
        <div className="flex flex-col items-center text-center">
          <h2 className="text-xl text-slate-400 mb-2 uppercase tracking-widest">Your Position</h2>
          <motion.div 
            key={position}
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="text-8xl md:text-[12rem] font-black text-transparent bg-clip-text bg-gradient-to-br from-white via-slate-200 to-slate-500 drop-shadow-2xl mb-8"
          >
            {position !== null ? position : '...'}
          </motion.div>
          <p className="text-slate-400 max-w-md">
            Do not refresh this page. You will be automatically redirected once it is your turn to checkout.
          </p>
          <div className="mt-12 flex space-x-2">
            <div className="w-2 h-2 rounded-full bg-purple-500 animate-bounce" style={{ animationDelay: '0ms' }} />
            <div className="w-2 h-2 rounded-full bg-purple-500 animate-bounce" style={{ animationDelay: '150ms' }} />
            <div className="w-2 h-2 rounded-full bg-purple-500 animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        </div>
      )}

      {status === 'allocated' && (
        <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="text-center">
          <div className="w-24 h-24 bg-green-500/20 text-green-400 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
          </div>
          <h2 className="text-4xl font-bold mb-4">Tickets Secured!</h2>
          <p className="text-slate-400 mb-2">You have been allocated a seat.</p>
          <p className="text-purple-400 font-bold animate-pulse">Redirecting to checkout...</p>
        </motion.div>
      )}

      {status === 'sold_out' && (
        <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="text-center">
          <div className="w-24 h-24 bg-red-500/20 text-red-400 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" /></svg>
          </div>
          <h2 className="text-4xl font-bold mb-4">Sold Out</h2>
          <p className="text-slate-400">Unfortunately, all seats were allocated before your turn.</p>
        </motion.div>
      )}

      {status === 'already_allocated' && (
        <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="text-center">
          <div className="w-24 h-24 bg-yellow-500/20 text-yellow-400 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
          </div>
          <h2 className="text-4xl font-bold mb-4">Limit Reached</h2>
          <p className="text-slate-400">You have already secured a ticket for this event. 1 Ticket per user.</p>
        </motion.div>
      )}
    </div>
  );
};
