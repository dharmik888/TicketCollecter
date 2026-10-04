# Fair Drop

Fair Drop is a high-demand sale and registration platform designed to prevent automated bots from gaining an unfair advantage over real users during "flash crowd" events (e.g., selling 500 tickets to 50,000 people).

## Architecture

The project is structured as a monorepo containing a Node.js backend and a React frontend.

### Tech Stack

*   **Frontend**: React, Vite, TypeScript, Tailwind CSS
*   **Backend**: Node.js, Express, TypeScript, Socket.IO
*   **Database**: SQLite (for persistent data)
*   **Caching/State**: In-memory Redis mock (to avoid external dependencies for the hackathon demo)
*   **Real-time Communication**: WebSockets via Socket.IO

### Project Structure

*   `/frontend` - The user interface where users will queue and attempt to purchase.
*   `/backend` - The server handling queuing logic, websocket connections, and database interactions.

## Getting Started

### Prerequisites

*   Node.js (v18 or higher recommended)

### Installation

1.  Install dependencies for the root, backend, and frontend:
    ```bash
    npm run install:all
    ```

### Running the Application

To run both the backend and frontend concurrently in development mode:

```bash
npm run dev
```

Alternatively, you can run them separately:
*   Backend: `npm run dev:backend`
*   Frontend: `npm run dev:frontend`
