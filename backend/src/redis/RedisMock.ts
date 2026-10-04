class RedisMock {
  private kvStore = new Map<string, string>();
  // zsets: key -> sorted array of { member, score }
  private zsets = new Map<string, { member: string; score: number }[]>();
  // sets: key -> Set of members
  private sets = new Map<string, Set<string>>();

  get(key: string): string | null {
    return this.kvStore.get(key) || null;
  }

  set(key: string, value: string): void {
    this.kvStore.set(key, value);
  }

  decr(key: string): number {
    let val = parseInt(this.kvStore.get(key) || '0', 10);
    if (isNaN(val)) val = 0;
    val -= 1;
    this.kvStore.set(key, val.toString());
    return val;
  }

  incr(key: string): number {
    let val = parseInt(this.kvStore.get(key) || '0', 10);
    if (isNaN(val)) val = 0;
    val += 1;
    this.kvStore.set(key, val.toString());
    return val;
  }

  zadd(key: string, score: number, member: string): void {
    if (!this.zsets.has(key)) {
      this.zsets.set(key, []);
    }
    const zset = this.zsets.get(key)!;
    const existingIndex = zset.findIndex((item) => item.member === member);
    
    if (existingIndex !== -1) {
      zset[existingIndex].score = score;
    } else {
      zset.push({ member, score });
    }
    
    // Sort ascending by score
    zset.sort((a, b) => a.score - b.score);
  }

  zrank(key: string, member: string): number | null {
    const zset = this.zsets.get(key);
    if (!zset) return null;
    
    const index = zset.findIndex((item) => item.member === member);
    return index !== -1 ? index : null;
  }

  zrange(key: string): string[] {
    const zset = this.zsets.get(key);
    return zset ? zset.map(item => item.member) : [];
  }

  zcard(key: string): number {
    const zset = this.zsets.get(key);
    return zset ? zset.length : 0;
  }

  zpopmin(key: string, count: number): { member: string; score: number }[] {
    const zset = this.zsets.get(key);
    if (!zset || zset.length === 0) return [];
    return zset.splice(0, count);
  }

  zremrangebyscore(key: string, min: number, max: number): void {
    const zset = this.zsets.get(key);
    if (!zset) return;
    this.zsets.set(key, zset.filter(item => item.score < min || item.score > max));
  }

  zcount(key: string, min: number, max: number): number {
    const zset = this.zsets.get(key);
    if (!zset) return 0;
    return zset.filter(item => item.score >= min && item.score <= max).length;
  }

  sadd(key: string, member: string): void {
    if (!this.sets.has(key)) {
      this.sets.set(key, new Set<string>());
    }
    this.sets.get(key)!.add(member);
  }

  sismember(key: string, member: string): number {
    const set = this.sets.get(key);
    if (!set) return 0;
    return set.has(member) ? 1 : 0;
  }
}

export const redis = new RedisMock();
