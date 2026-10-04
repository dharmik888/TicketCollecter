import { redis } from '../redis/RedisMock';

export class QueueService {
  /**
   * Add a user to the event's queue using a Randomized Weighted Lottery Algorithm.
   * Instead of First-Come-First-Serve, users receive a random lottery ticket number.
   * The system heavily biases the randomization in favor of real fans over bots.
   */
  static enqueueUser(eventId: string, userId: string, botScore: number = 0) {
    const key = `queue:${eventId}`;
    
    // Base lottery ticket: a random number between 0 and 10000.
    // Lower number = closer to the front of the queue.
    const baseLottery = Math.random() * 10000;
    
    // Real fans (botScore ~ 0.0) keep their good lottery numbers.
    // Bots (botScore ~ 1.0) get severely penalized with a massive addition to their lottery score.
    // This randomization prevents bot swarms from dominating the front of the line.
    const randomizedScore = baseLottery + (botScore * 1000000);
    
    redis.zadd(key, randomizedScore, userId);
  }

  /**
   * Get 1-indexed position of a user in the queue
   */
  static getPosition(eventId: string, userId: string): number | null {
    const key = `queue:${eventId}`;
    const rank = redis.zrank(key, userId);
    // zrank is 0-indexed, so we add 1 for human readable queue position
    return rank !== null ? rank + 1 : null;
  }

  /**
   * Get the total length of the queue
   */
  static getQueueLength(eventId: string): number {
    const key = `queue:${eventId}`;
    return redis.zcard(key);
  }
}
