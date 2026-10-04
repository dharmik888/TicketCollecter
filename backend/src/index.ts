import 'dotenv/config';
import express from 'express';
import http from 'http';
import { Server } from 'socket.io';
import cors from 'cors';
import jwt from 'jsonwebtoken';
import { QueueService } from './services/QueueService';
import { AllocationService } from './services/AllocationService';
import { db } from './db/Database';
import { redis } from './redis/RedisMock';

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: "*", // Configure this properly in production
    methods: ["GET", "POST"]
  }
});

import { rateLimiter } from './middleware/rateLimiter';
import { BotDetector } from './services/BotDetector';
import { powRoutes } from './routes/pow';
import { authRoutes } from './routes/auth';
import { eventRoutes } from './routes/events';

app.use(cors());
app.use(express.json());

// Apply global rate limiting: max 100 requests per 1 minute window
app.use(rateLimiter({ windowMs: 60 * 1000, max: 100 }));

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/events', eventRoutes);
app.use('/api/allocation', powRoutes);

const PORT = process.env.PORT || 3001;

// Basic health check endpoint
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', message: 'Fair Drop API is running' });
});

const JWT_SECRET = 'super-secret-key-for-hackathon';

// Socket.io JWT Authentication Middleware
io.use((socket, next) => {
  const token = socket.handshake.auth.token;
  if (!token) {
    return next(new Error('Authentication error: Token missing'));
  }
  try {
    const decoded = jwt.verify(token, JWT_SECRET) as { userId: string };
    socket.data.userId = decoded.userId;
    next();
  } catch (err) {
    next(new Error('Authentication error: Invalid token'));
  }
});

// WebSocket connection handling
io.on('connection', (socket) => {
  const userId = socket.data.userId;
  console.log(`User connected: ${userId}`);

  // 1. Join personal room to easily message this user directly
  socket.join(userId);

  // 2. Listen for 'join_queue' event
  socket.on('join_queue', (data) => {
    const { eventId } = data;
    if (!eventId) return;

    // Check Proof of Work
    const powVerified = redis.get(`pow_verified:${userId}`);
    if (powVerified !== 'true') {
      socket.emit('bot_detected', { message: 'PoW verification missing or expired. Connection closed.' });
      socket.disconnect();
      return;
    }

    // Check if they already secured a ticket previously
    if (redis.sismember(`allocated:${eventId}`, userId) === 1) {
      socket.emit('allocation_result', { eventId, status: 'already_allocated' });
      socket.disconnect();
      return;
    }

    // Enqueue the user (pass their ML bot score to dynamically adjust their rank!)
    const currentBotScore = socket.data.botScore || 0;
    QueueService.enqueueUser(eventId, userId, currentBotScore);
    
    // Get their new position
    const position = QueueService.getPosition(eventId, userId);
    
    // Emit the position back exclusively to the user's room
    io.to(userId).emit('queue_update', { eventId, position });
  });

  // 3. Listen for behavioral data telemetry
  socket.on('behavior_data', async (data) => {
    const botScore = await BotDetector.analyzeBehavior(userId, data);
    console.log(`User ${userId} behavior scored: ${botScore.toFixed(2)}`);
    
    if (botScore >= 0.8) {
      // High probability of bot -> disconnect
      socket.emit('bot_detected', { message: 'Suspicious activity detected. Connection closed.' });
      socket.disconnect();
    } else {
      socket.data.botScore = botScore;
    }
  });

  socket.on('disconnect', () => {
    console.log(`User disconnected: ${userId}`);
  });
});

// Background Interval: Broadcast event status every 5 seconds (Fixes Network Broadcast Storms)
setInterval(async () => {
  // Find all ACTIVE events
  const activeEvents = await db.getActiveEvents();
  
  for (const event of activeEvents) {
    // Auto-close if expired
    if (event.expires_at && Date.now() > event.expires_at) {
      event.status = 'CLOSED';
      await db.updateEvent(event);
      // Use volatile to drop packets instead of crashing the network buffer on massive scale
      io.volatile.emit('event_status', {
        eventId: event.id,
        status: 'CLOSED'
      });
      continue;
    }

    const queueLength = QueueService.getQueueLength(event.id);
    
    // Broadcast to all connected clients using volatile (unreliable but prevents choking)
    io.volatile.emit('event_status', {
      eventId: event.id,
      available_seats: event.available_seats,
      queue_length: queueLength,
      expires_at: event.expires_at
    });
  }
}, 5000);

// Background Worker: Process queue batches every 1 second
setInterval(async () => {
  const activeEvents = await db.getActiveEvents();
  
  for (const event of activeEvents) {
    const queueKey = `queue:${event.id}`;
    // Pop a batch of 10 users to process
    const usersToProcess = redis.zpopmin(queueKey, 10);
    
    for (const { member: userId } of usersToProcess) {
      const result = await AllocationService.allocateSeat(event.id, userId);
      // Emit result back to the specific user via WebSockets
      io.to(userId).emit('allocation_result', { 
        eventId: event.id, 
        status: result 
      });
    }
  }
}, 1000);

server.listen(PORT, () => {
  console.log(`Backend server listening on port ${PORT}`);
});
