import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { Footer } from './components/Footer';
import { AuthModal } from './components/AuthModal';
import { HomePage } from './pages/HomePage';
import { EventDetailPage } from './pages/EventDetailPage';
import { QueueRoomPage } from './pages/QueueRoomPage';
import { CheckoutPage } from './pages/CheckoutPage';
import { BookingsPage } from './pages/BookingsPage';
import { StaffPage } from './pages/StaffPage';

export function App() {
  const [currentPath, setCurrentPath] = useState(() => {
    const hash = window.location.hash.replace(/^#/, '');
    return hash || '/';
  });

  const [isAuthOpen, setIsAuthOpen] = useState(() => {
    return !localStorage.getItem('fairdrop-session');
  });

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace(/^#/, '');
      setCurrentPath(hash || '/');
      window.scrollTo(0, 0);
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigate = (path) => {
    window.location.hash = path;
    setCurrentPath(path);
    window.scrollTo(0, 0);
  };

  // Route matching
  const renderPage = () => {
    if (currentPath === '/' || currentPath === '') {
      return <HomePage onNavigate={navigate} />;
    }

    if (currentPath.startsWith('/event/')) {
      const eventId = currentPath.replace('/event/', '');
      return <EventDetailPage eventId={eventId} onNavigate={navigate} />;
    }

    if (currentPath.startsWith('/queue/')) {
      const eventId = currentPath.replace('/queue/', '');
      return <QueueRoomPage eventId={eventId} onNavigate={navigate} />;
    }

    if (currentPath.startsWith('/checkout/')) {
      const eventId = currentPath.replace('/checkout/', '');
      return <CheckoutPage eventId={eventId} onNavigate={navigate} />;
    }

    if (currentPath === '/bookings') {
      return <BookingsPage onNavigate={navigate} />;
    }

    if (currentPath === '/staff') {
      return <StaffPage onNavigate={navigate} />;
    }

    // Default fallback to HomePage
    return <HomePage onNavigate={navigate} />;
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
      <div>
        <Header
          currentRoute={currentPath}
          onNavigate={navigate}
          onOpenAuth={() => setIsAuthOpen(true)}
        />
        {renderPage()}
      </div>

      <Footer />

      <AuthModal isOpen={isAuthOpen} onClose={() => setIsAuthOpen(false)} />
    </div>
  );
}
export default App;
