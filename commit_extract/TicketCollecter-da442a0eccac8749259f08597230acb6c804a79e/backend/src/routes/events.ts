import express from 'express';
import { db, Event } from '../db/Database';
import { redis } from '../redis/RedisMock';

const router = express.Router();

router.post('/', (req, res) => {
  const { name, total_seats, duration_minutes } = req.body;

  if (!name || !total_seats) {
    return res.status(400).json({ error: 'Name and total_seats required' });
  }

  const id = Math.random().toString(36).substring(2, 15);
  const newEvent: Event = {
    id,
    name,
    total_seats,
    available_seats: total_seats,
    status: 'PENDING',
    duration_minutes
  };

  db.events.set(id, newEvent);
  res.status(201).json(newEvent);
});

router.get('/', (req, res) => {
  const events = Array.from(db.events.values());
  res.json(events);
});

router.get('/user/bookings', (req, res) => {
  const userId = req.headers['user-id'] as string;
  if (!userId) return res.status(401).json({ error: 'Unauthorized' });

  const allAllocations = Array.from(db.allocations.values()).filter(a => a.user_id === userId);
  const populated = allAllocations.map(a => {
    const event = db.events.get(a.event_id);
    return {
      ...a,
      eventName: event ? event.name : 'Unknown Event'
    };
  });
  res.json(populated);
});

router.get('/:id', (req, res) => {
  const event = db.events.get(req.params.id);
  if (!event) {
    return res.status(404).json({ error: 'Event not found' });
  }
  res.json(event);
});

// For hackathon testing - manually open an event
router.post('/:id/open', (req, res) => {
  const event = db.events.get(req.params.id);
  if (!event) {
    return res.status(404).json({ error: 'Event not found' });
  }
  
  event.status = 'ACTIVE';
  if (event.duration_minutes) {
    event.expires_at = Date.now() + event.duration_minutes * 60000;
  }
  
  redis.set(`seats:${event.id}`, event.available_seats.toString());
  res.json(event);
});

router.post('/:id/stop', (req, res) => {
  const event = db.events.get(req.params.id);
  if (!event) {
    return res.status(404).json({ error: 'Event not found' });
  }
  
  event.status = 'CLOSED';
  res.json(event);
});

router.post('/:id/checkout', (req, res) => {
  const eventId = req.params.id;
  const userId = req.headers['user-id'] as string;
  const { paymentAccountId } = req.body;
  
  if (!paymentAccountId) {
    return res.status(400).json({ error: 'Payment account details are required.' });
  }

  // Prevent same payment account from being used twice for the same event
  if (redis.sismember(`used_payment:${eventId}`, paymentAccountId) === 1) {
    return res.status(400).json({ error: 'This payment account has already been used to purchase a ticket for this event.' });
  }

  const allocation = Array.from(db.allocations.values()).find(a => a.event_id === eventId && a.user_id === userId);
  if (!allocation) return res.status(404).json({ error: 'Allocation not found' });

  if (allocation.status !== 'RESERVED') {
    return res.status(400).json({ error: 'Ticket is already ' + allocation.status });
  }

  // Lock in the payment account
  redis.sadd(`used_payment:${eventId}`, paymentAccountId);

  allocation.status = 'CONFIRMED';
  res.json({ success: true, ticket: allocation });
});

router.get('/:id/queue-details', (req, res) => {
  const eventId = req.params.id;
  const userIds = redis.zrange(`queue:${eventId}`);
  const details = userIds.map(userId => {
    const data = redis.get(`details:${eventId}:${userId}`);
    return data ? { userId, ...JSON.parse(data) } : { userId };
  });
  res.json(details);
});

router.post('/:id/register-details', (req, res) => {
  const { fullName, phoneNumber, emailId, address } = req.body;
  const userId = req.headers['user-id'] as string;
  const eventId = req.params.id;
  
  if (!userId || !fullName || !phoneNumber || !emailId || !address) {
    return res.status(400).json({ error: 'Missing all required details.' });
  }

  // Prevent buying if they already have a ticket
  if (redis.sismember(`allocated:${eventId}`, userId) === 1) {
    return res.status(400).json({ error: 'You already have a ticket for this event.' });
  }

  // Prevent Sybil attacks: Ensure phone, email, and address are strictly unique per event
  if (redis.sismember(`used_phone:${eventId}`, phoneNumber) === 1) {
    return res.status(400).json({ error: 'This phone number is already registered for this event.' });
  }
  if (redis.sismember(`used_email:${eventId}`, emailId) === 1) {
    return res.status(400).json({ error: 'This email is already registered for this event.' });
  }
  if (redis.sismember(`used_address:${eventId}`, address) === 1) {
    return res.status(400).json({ error: 'This address is already registered for this event.' });
  }

  // Lock in the unique details
  redis.sadd(`used_phone:${eventId}`, phoneNumber);
  redis.sadd(`used_email:${eventId}`, emailId);
  redis.sadd(`used_address:${eventId}`, address);

  // Store user shipping details for this specific drop
  redis.set(`details:${eventId}:${userId}`, JSON.stringify({ fullName, phoneNumber, emailId, address }));
  res.json({ success: true });
});

export const eventRoutes = router;
