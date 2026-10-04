import { create } from 'zustand';

export interface Event {
  id: string;
  name: string;
  total_seats: number;
  available_seats: number;
  status: 'PENDING' | 'ACTIVE' | 'CLOSED';
}

interface EventState {
  events: Event[];
  setEvents: (events: Event[]) => void;
  updateEventStats: (eventId: string, availableSeats: number, queueLength: number) => void;
}

export const useEventStore = create<EventState>((set) => ({
  events: [],
  setEvents: (events) => set({ events }),
  updateEventStats: (eventId, availableSeats, queueLength) => 
    set((state) => ({
      events: state.events.map(e => 
        e.id === eventId 
          ? { ...e, available_seats: availableSeats, _queueLength: queueLength } 
          : e
      )
    }))
}));
