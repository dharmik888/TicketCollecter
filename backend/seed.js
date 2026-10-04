const http = require('http');

const events = [
  {
    id: 'neon-night',
    name: 'Neon Night Market',
    tag: 'SYNTHWAVE',
    date: 'Sat · 8:00 PM · Warehouse 9',
    price: '₹1,499',
    priceNum: 1499,
    total_seats: 500,
    duration_minutes: 90,
    image: '/assets/event-synthwave-BfV0-GEt.jpg',
    description: 'An immersive retro-futuristic audio-visual experience with live synthwave artists, neon installations, and cyberpunk night market food stalls.'
  },
  {
    id: 'rooftop-blue',
    name: 'Rooftop Blue Trio',
    tag: 'JAZZ',
    date: 'Fri · 9:30 PM · Skyline Deck',
    price: '₹899',
    priceNum: 899,
    total_seats: 120,
    duration_minutes: 60,
    image: '/assets/event-jazz-CCYVK6-g.jpg',
    description: 'Intimate evening jazz under the city skyline. Featuring classical saxophone, upright bass, and vintage piano arrangements.'
  },
  {
    id: 'late-laughs',
    name: 'Late Laughs Live',
    tag: 'COMEDY',
    date: 'Sun · 7:00 PM · The Basement',
    price: '₹649',
    priceNum: 649,
    total_seats: 240,
    duration_minutes: 45,
    image: '/assets/event-comedy-Bb4-fimN.jpg',
    description: 'Unfiltered, high-energy stand-up comedy showcase featuring top touring comedians and surprise special guests.'
  }
];

async function seed() {
  for (const ev of events) {
    const data = Buffer.from(JSON.stringify(ev), 'utf8');
    await new Promise((resolve) => {
      const req = http.request({
        hostname: 'localhost',
        port: 3001,
        path: '/api/events',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': data.length
        }
      }, (res) => {
        res.on('data', () => {});
        res.on('end', async () => {
          // Open the event
          const openReq = http.request({
            hostname: 'localhost',
            port: 3001,
            path: `/api/events/${ev.id}/open`,
            method: 'POST',
          }, (res2) => {
            res2.on('data', () => {});
            res2.on('end', resolve);
          });
          openReq.end();
        });
      });
      req.write(data);
      req.end();
    });
    console.log(`Seeded and opened event: ${ev.name}`);
  }
}

seed().catch(console.error);
