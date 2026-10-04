import { redis } from '../redis/RedisMock';
import { db, Allocation } from '../db/Database';

export class AllocationService {
  /**
   * Attempts to allocate a seat for a user.
   * Decrements Redis seat count to avoid race conditions and overselling.
   */
  static async allocateSeat(eventId: string, userId: string): Promise<'success' | 'sold_out' | 'already_allocated'> {
    const allocatedKey = `allocated:${eventId}`;
    
    // 1. Check if user already has a seat
    if (redis.sismember(allocatedKey, userId) === 1) {
      return 'already_allocated';
    }

    // 2. Decrement available seats atomically (simulated via Redis Mock)
    const seatsKey = `seats:${eventId}`;
    const remaining = redis.decr(seatsKey);

    if (remaining < 0) {
      // 3. Rollback atomically: If it drops below 0, we're sold out
      redis.incr(seatsKey);
      return 'sold_out';
    }

    // 4. Add user to allocated set
    redis.sadd(allocatedKey, userId);

    // 5. Update SQLite/Mock DB
    const event = await db.getEvent(eventId);
    if (event) {
      event.available_seats = remaining;
      await db.updateEvent(event);
    }

    const allocationId = Math.random().toString(36).substring(2, 15);
    const newAllocation: Allocation = {
      id: allocationId,
      event_id: eventId,
      user_id: userId,
      status: 'RESERVED'
    };
    await db.createAllocation(newAllocation);

    return 'success';
  }
}
