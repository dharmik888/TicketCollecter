import { Request, Response, NextFunction } from 'express';
import { redis } from '../redis/RedisMock';

export const rateLimiter = (options: { windowMs: number, max: number }) => {
  return (req: Request, res: Response, next: NextFunction) => {
    const ip = req.ip || 'unknown';
    const key = `ratelimit:${ip}`;
    const now = Date.now();
    const windowStart = now - options.windowMs;

    // 1. Remove old requests outside the sliding window
    redis.zremrangebyscore(key, 0, windowStart);

    // 2. Count current requests inside the window
    const requestCount = redis.zcount(key, windowStart, now);

    if (requestCount >= options.max) {
      return res.status(429).json({ error: 'Too many requests, please try again later.' });
    }

    // 3. Log the current request
    // We add a random suffix so unique requests with the exact same millisecond timestamp don't overwrite each other in the ZSET.
    redis.zadd(key, now, `${now}-${Math.random()}`);
    
    next();
  };
};
