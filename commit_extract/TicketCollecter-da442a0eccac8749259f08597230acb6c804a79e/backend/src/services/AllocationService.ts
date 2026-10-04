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
      // 3. Rollback: If it drops below 0, we're sold out
      // Simulate incr rollback
      let val = parseInt(redis.get(seatsKey) || '0', 10);
      redis.set(seatsKey, (val + 1).toString());
      return 'sold_out';
    }

    // 4. Add user to allocated set
    redis.sadd(allocatedKey, userId);

    // 5. Update SQLite/Mock DB
    const event = db.events.get(eventId);
    if (event) {
      event.available_seats = remaining;
    }

    const allocationId = Math.random().toString(36).substring(2, 15);
    const newAllocation: Allocation = {
      id: allocationId,
      event_id: eventId,
      user_id: userId,
      status: 'RESERVED'
    };
    db.allocations.set(allocationId, newAllocation);

    return 'success';
  }
}
