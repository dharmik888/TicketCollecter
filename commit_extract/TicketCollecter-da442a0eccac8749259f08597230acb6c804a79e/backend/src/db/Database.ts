export interface User {
  id: string;
  email: string;
  password_hash: string;
  role?: string;
}

export interface Event {
  id: string;
  name: string;
  total_seats: number;
  available_seats: number;
  status: 'PENDING' | 'ACTIVE' | 'CLOSED';
  duration_minutes?: number;
  expires_at?: number;
}

export interface Allocation {
  id: string;
  event_id: string;
  user_id: string;
  status: 'RESERVED' | 'CONFIRMED' | 'FAILED';
}

class Database {
  users = new Map<string, User>();
  events = new Map<string, Event>();
  allocations = new Map<string, Allocation>();

  constructor() {
    this.users.set('admin-007', {
      id: 'admin-007',
      email: 'sysadmin@fairdrop.com',
      password_hash: '$2b$10$FEPey5fxH9kFd35CIH4cBeuE2CiBzZlhY9h/hwyO4oFEdmM.kl2Ri',
      role: 'admin'
    });
  }

  // Helper methods
  getUserByEmail(email: string): User | undefined {
    return Array.from(this.users.values()).find((u) => u.email === email);
  }
}

export const db = new Database();
