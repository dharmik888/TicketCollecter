import express from 'express';
import crypto from 'crypto';
import { redis } from '../redis/RedisMock';

const router = express.Router();
const DIFFICULTY = 4; // Number of leading zeros required

router.get('/challenge', (req, res) => {
  // Use user-id header if available, otherwise IP
  const userId = req.headers['user-id'] as string || req.ip || 'unknown'; 
  const challenge = crypto.randomBytes(16).toString('hex');
  
  // Store the challenge for this user (could add expiration in a real redis)
  redis.set(`pow:${userId}`, challenge);
  
  res.json({ challenge, difficulty: DIFFICULTY });
});

router.post('/verify-pow', (req, res) => {
  const userId = req.headers['user-id'] as string || req.ip || 'unknown'; 
  const { nonce } = req.body;
  const challenge = redis.get(`pow:${userId}`);

  if (!challenge) {
    return res.status(400).json({ error: 'Challenge not found or expired' });
  }

  if (!nonce) {
    return res.status(400).json({ error: 'Nonce required' });
  }

  const hash = crypto.createHash('sha256').update(challenge + nonce).digest('hex');
  const target = '0'.repeat(DIFFICULTY);

  if (hash.startsWith(target)) {
    // PoW Verified successfully
    redis.set(`pow_verified:${userId}`, 'true');
    res.json({ success: true, message: 'Proof of Work verified successfully.' });
  } else {
    res.status(401).json({ error: 'Invalid Proof of Work' });
  }
});

export const powRoutes = router;
