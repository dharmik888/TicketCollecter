import { io } from 'socket.io-client';
import jwt from 'jsonwebtoken';
import axios from 'axios';
import crypto from 'crypto';

const JWT_SECRET = 'super-secret-key-for-hackathon';

async function getEventId() {
  const res = await axios.get('http://localhost:3001/api/events');
  if (res.data.length > 0) return res.data[0].id;
  throw new Error("No events found. Please create one in the admin dashboard.");
}

async function solvePoW(challenge: string, difficulty: number): Promise<number> {
  const target = '0'.repeat(difficulty);
  let nonce = 0;
  while (true) {
    const hash = crypto.createHash('sha256').update(challenge + nonce).digest('hex');
    if (hash.startsWith(target)) {
      return nonce;
    }
    nonce++;
  }
}

async function simulateNormalUser(i: number, eventId: string) {
  const userId = `human-${i}`;
  const token = jwt.sign({ userId }, JWT_SECRET);
  
  try {
    // 1. Fetch Challenge
    const challengeRes = await axios.get('http://localhost:3001/api/allocation/challenge', {
      headers: { 'user-id': userId }
    });
    const { challenge, difficulty } = challengeRes.data;
    
    // 2. Solve Challenge
    console.log(`[Human ${i}] 🧩 Solving cryptographic puzzle...`);
    const nonce = await solvePoW(challenge, difficulty);
    
    // 3. Verify
    await axios.post('http://localhost:3001/api/allocation/verify-pow', 
      { nonce }, 
      { headers: { 'user-id': userId } }
    );
    console.log(`[Human ${i}] ✅ Verification passed! Joining real-time queue...`);
    
    // 4. Connect to WebSockets
    const socket = io('http://localhost:3001', { 
      auth: { token },
      transports: ['websocket']
    });
    
    socket.on('connect', () => {
      socket.emit('join_queue', { eventId });
    });
    
    socket.on('queue_update', (data) => {
      console.log(`[Human ${i}] 🎫 Position in Queue: ${data.position}`);
    });
    
    socket.on('allocation_result', (data) => {
      console.log(`[Human ${i}] 🎉 Status: ${data.status.toUpperCase()}`);
      if (data.status === 'success') {
        socket.disconnect();
      }
    });
    
    socket.on('bot_detected', (data) => {
      console.log(`[Human ${i}] ❌ Mistakenly flagged as bot: ${data.message}`);
    });
    
    // 5. Send normal human behavior telemetry every 5 seconds
    setInterval(() => {
      socket.emit('behavior_data', {
        mouse_movements: Math.floor(Math.random() * 20),
        keystrokes: 0,
        scroll_events: Math.floor(Math.random() * 2),
        session_duration_ms: 5000
      });
    }, 5000);
    
  } catch (e: any) {
    console.error(`[Human ${i}] Error:`, e.response?.data?.error || e.message);
  }
}

async function run() {
  try {
    const eventId = await getEventId();
    console.log(`👤 Commencing NORMAL USERS: Spawning 10 humans for event ${eventId}`);
    
    for (let i = 1; i <= 10; i++) {
      // Stagger them slightly
      setTimeout(() => simulateNormalUser(i, eventId), i * 800);
    }
  } catch(e: any) {
    console.error(e.message);
  }
}

run();
