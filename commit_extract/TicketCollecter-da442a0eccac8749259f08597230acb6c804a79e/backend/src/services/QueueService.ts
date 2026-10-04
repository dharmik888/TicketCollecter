import { redis } from '../redis/RedisMock';

export class QueueService {
  /**
   * Add a user to the event's queue based on the current timestamp
   */
  static enqueueUser(eventId: string, userId: string) {
    const key = `queue:${eventId}`;
    // Score is timestamp, prioritizing earlier additions
    redis.zadd(key, Date.now(), userId);
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
