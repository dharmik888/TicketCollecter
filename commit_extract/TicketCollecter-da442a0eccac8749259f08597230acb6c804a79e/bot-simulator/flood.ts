import { io } from 'socket.io-client';
import jwt from 'jsonwebtoken';
import axios from 'axios';

const JWT_SECRET = 'super-secret-key-for-hackathon';

async function getEventId() {
  const res = await axios.get('http://localhost:3001/api/events');
  if (res.data.length > 0) return res.data[0].id;
  throw new Error("No events found. Please create one in the admin dashboard.");
}

async function flood() {
  console.log("🌊 Commencing BOT FLOOD: Spawning 100 simultaneous connections...");
  
  try {
    const eventId = await getEventId();
    let rejectedCount = 0;
    
    for (let i = 0; i < 100; i++) {
      const userId = `bot-${i}`;
      const token = jwt.sign({ userId }, JWT_SECRET);
      
      const socket = io('http://localhost:3001', {
        auth: { token },
        transports: ['websocket']
      });

      socket.on('connect', () => {
        // Instantly try to join the queue WITHOUT doing the Proof of Work
        socket.emit('join_queue', { eventId });
        
        // Concurrently emit highly impossible robotic behavior data
        socket.emit('behavior_data', {
          mouse_movements: 500, // 500 movements in 10ms
          keystrokes: 200,
          scroll_events: 100,
          session_duration_ms: 10
        });
      });

      socket.on('bot_detected', (data) => {
        rejectedCount++;
        console.log(`[BOT ${i}] ❌ BUSTED by system: ${data.message}`);
      });
      
      socket.on('queue_update', () => {
        console.log(`[BOT ${i}] 🚨 WARNING: Bot somehow joined the queue!`);
      });
    }
  } catch (e: any) {
    console.error(e.message);
  }
}

flood();
