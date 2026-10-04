"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const socket_io_client_1 = require("socket.io-client");
const jsonwebtoken_1 = __importDefault(require("jsonwebtoken"));
const axios_1 = __importDefault(require("axios"));
const JWT_SECRET = 'super-secret-key-for-hackathon';
async function getEventId() {
    const res = await axios_1.default.get('http://localhost:3001/api/events');
    if (res.data.length > 0)
        return res.data[0].id;
    throw new Error("No events found. Please create one in the admin dashboard.");
}
async function flood() {
    console.log("🌊 Commencing BOT FLOOD: Spawning 100 simultaneous connections...");
    try {
        const eventId = await getEventId();
        let rejectedCount = 0;
        for (let i = 0; i < 100; i++) {
            const userId = `bot-${i}`;
            const token = jsonwebtoken_1.default.sign({ userId }, JWT_SECRET);
            const socket = (0, socket_io_client_1.io)('http://localhost:3001', {
                auth: { token },
                transports: ['websocket']
            });
            socket.on('connect', () => {
                // Instantly try to join the queue WITHOUT doing the Proof of Work
                socket.emit('join_queue', { eventId });
                // Concurrently emit highly impossible robotic behavior data
                socket.emit('behavior_data', {
                    mouse_movements: 500, // 500 movements in 10ms
                    keystrokes: 200,
                    scroll_events: 100,
                    session_duration_ms: 10
                });
            });
            socket.on('bot_detected', (data) => {
                rejectedCount++;
                console.log(`[BOT ${i}] ❌ BUSTED by system: ${data.message}`);
            });
            socket.on('queue_update', () => {
                console.log(`[BOT ${i}] 🚨 WARNING: Bot somehow joined the queue!`);
            });
        }
    }
    catch (e) {
        console.error(e.message);
    }
}
flood();
