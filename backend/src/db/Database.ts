import sqlite3 from 'sqlite3';

export interface User {
  id: string;
  email: string;
  password_hash: string;
  role?: string;
}

export interface Event {
  id: string;
  name: string;
  tag?: string;
  date?: string;
  price?: string;
  priceNum?: number;
  image?: string;
  description?: string;
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

class TaskQueue {
  private queue: (() => Promise<void>)[] = [];
  private isProcessing = false;

  async enqueue<T>(task: () => Promise<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      this.queue.push(async () => {
        try {
          resolve(await task());
        } catch (e) {
          reject(e);
        }
      });
      this.process();
    });
  }

  private async process() {
    if (this.isProcessing || this.queue.length === 0) return;
    this.isProcessing = true;
    while (this.queue.length > 0) {
      const task = this.queue.shift();
      if (task) await task();
    }
    this.isProcessing = false;
  }
}

class Database {
  private db: sqlite3.Database;
  private writeQueue = new TaskQueue();

  constructor() {
    this.db = new sqlite3.Database('database.sqlite', (err) => {
      if (err) console.error('Error opening db', err);
      else {
        // Prevent deadlocks and "SQLITE_BUSY" when 50000 users connect
        this.db.run('PRAGMA journal_mode = WAL;');
        this.db.run('PRAGMA busy_timeout = 5000;');
        this.init();
      }
    });
  }

  private init() {
    this.db.serialize(() => {
      this.db.run(`CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE,
        password_hash TEXT,
        role TEXT
      )`);

      this.db.run(`CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        name TEXT,
        tag TEXT,
        date TEXT,
        price TEXT,
        priceNum INTEGER,
        image TEXT,
        description TEXT,
        total_seats INTEGER,
        available_seats INTEGER,
        status TEXT,
        duration_minutes INTEGER,
        expires_at INTEGER
      )`);

      this.db.run(`CREATE TABLE IF NOT EXISTS allocations (
        id TEXT PRIMARY KEY,
        event_id TEXT,
        user_id TEXT,
        status TEXT
      )`);
      
      // Insert admin user if environment variables are provided
      const adminEmail = process.env.ADMIN_EMAIL;
      const adminHash = process.env.ADMIN_PASSWORD_HASH;
      if (adminEmail && adminHash) {
        this.db.run(`INSERT OR IGNORE INTO users (id, email, password_hash, role) VALUES ('admin-007', ?, ?, 'admin')`, [adminEmail, adminHash]);
      }
    });
  }

  // User methods
  async getUser(id: string): Promise<User | undefined> {
    return new Promise((resolve, reject) => {
      this.db.get('SELECT * FROM users WHERE id = ?', [id], (err, row) => {
        if (err) reject(err);
        else resolve(row as User);
      });
    });
  }

  async getUserByEmail(email: string): Promise<User | undefined> {
    return new Promise((resolve, reject) => {
      this.db.get('SELECT * FROM users WHERE email = ?', [email], (err, row) => {
        if (err) reject(err);
        else resolve(row as User);
      });
    });
  }

  async createUser(user: User): Promise<void> {
    return new Promise((resolve, reject) => {
      this.db.run('INSERT INTO users (id, email, password_hash, role) VALUES (?, ?, ?, ?)', [user.id, user.email, user.password_hash, user.role], (err) => {
        if (err) reject(err);
        else resolve();
      });
    });
  }
  
  // Event methods
  async getEvent(id: string): Promise<Event | undefined> {
    return new Promise((resolve, reject) => {
      this.db.get('SELECT * FROM events WHERE id = ?', [id], (err, row) => {
        if (err) reject(err);
        else resolve(row as Event);
      });
    });
  }

  async createEvent(event: Event): Promise<void> {
    return this.writeQueue.enqueue(() => new Promise((resolve, reject) => {
      this.db.run('INSERT INTO events (id, name, tag, date, price, priceNum, image, description, total_seats, available_seats, status, duration_minutes, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', 
        [event.id, event.name, event.tag || '', event.date || '', event.price || '', event.priceNum || 0, event.image || '', event.description || '', event.total_seats, event.available_seats, event.status, event.duration_minutes, event.expires_at], (err) => {
        if (err) reject(err);
        else resolve();
      });
    }));
  }
  
  async updateEvent(event: Event): Promise<void> {
    return this.writeQueue.enqueue(() => new Promise((resolve, reject) => {
      this.db.run('UPDATE events SET name = ?, tag = ?, date = ?, price = ?, priceNum = ?, image = ?, description = ?, total_seats = ?, available_seats = ?, status = ?, duration_minutes = ?, expires_at = ? WHERE id = ?', 
        [event.name, event.tag || '', event.date || '', event.price || '', event.priceNum || 0, event.image || '', event.description || '', event.total_seats, event.available_seats, event.status, event.duration_minutes, event.expires_at, event.id], (err) => {
        if (err) reject(err);
        else resolve();
      });
    }));
  }
  
  async getAllEvents(): Promise<Event[]> {
    return new Promise((resolve, reject) => {
      this.db.all('SELECT * FROM events', [], (err, rows) => {
        if (err) reject(err);
        else resolve(rows as Event[]);
      });
    });
  }

  async getActiveEvents(): Promise<Event[]> {
    return new Promise((resolve, reject) => {
      this.db.all('SELECT * FROM events WHERE status = ?', ['ACTIVE'], (err, rows) => {
        if (err) reject(err);
        else resolve(rows as Event[]);
      });
    });
  }

  // Allocation methods
  async getAllocation(id: string): Promise<Allocation | undefined> {
    return new Promise((resolve, reject) => {
      this.db.get('SELECT * FROM allocations WHERE id = ?', [id], (err, row) => {
        if (err) reject(err);
        else resolve(row as Allocation);
      });
    });
  }
  
  async getUserAllocationForEvent(userId: string, eventId: string): Promise<Allocation | undefined> {
    return new Promise((resolve, reject) => {
      this.db.get('SELECT * FROM allocations WHERE user_id = ? AND event_id = ?', [userId, eventId], (err, row) => {
        if (err) reject(err);
        else resolve(row as Allocation);
      });
    });
  }

  async createAllocation(allocation: Allocation): Promise<void> {
    return this.writeQueue.enqueue(() => new Promise((resolve, reject) => {
      this.db.run('INSERT INTO allocations (id, event_id, user_id, status) VALUES (?, ?, ?, ?)', [allocation.id, allocation.event_id, allocation.user_id, allocation.status], (err) => {
        if (err) reject(err);
        else resolve();
      });
    }));
  }
  
  async updateAllocationStatus(id: string, status: string): Promise<void> {
    return this.writeQueue.enqueue(() => new Promise((resolve, reject) => {
      this.db.run('UPDATE allocations SET status = ? WHERE id = ?', [status, id], (err) => {
        if (err) reject(err);
        else resolve();
      });
    }));
  }

  async getUserAllocations(userId: string): Promise<Allocation[]> {
    return new Promise((resolve, reject) => {
      this.db.all('SELECT * FROM allocations WHERE user_id = ?', [userId], (err, rows) => {
        if (err) reject(err);
        else resolve(rows as Allocation[]);
      });
    });
  }
}

export const db = new Database();
