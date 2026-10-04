import { BrowserRouter as Router, Routes, Route, useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import { LandingPage } from './pages/LandingPage';
import { WaitingRoom } from './pages/WaitingRoom';
import { AdminDashboard } from './pages/AdminDashboard';
import { AdminLogin } from './pages/AdminLogin';
import { Checkout } from './pages/Checkout';
import { MyBookings } from './pages/MyBookings';
import { useAuthStore } from './store/authStore';

const GlobalSecurity = () => {
  const { user } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    // If the user is an admin, do NOT block dev tools
    if (user?.role === 'admin') return;

    const handleContextMenu = (e: MouseEvent) => e.preventDefault();
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.key === 'F12' || 
        (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'J' || e.key === 'C')) || 
        (e.ctrlKey && e.key === 'U')
      ) {
        e.preventDefault();
      }
    };
    
    document.addEventListener('contextmenu', handleContextMenu);
    document.addEventListener('keydown', handleKeyDown);

    const devToolsInterval = setInterval(() => {
      const start = new Date().getTime();
      // eslint-disable-next-line no-debugger
      debugger;
      const end = new Date().getTime();
      if (end - start > 100) {
        // Devtools detected, send them to the main page
        navigate('/');
      }
    }, 1000);

    return () => {
      document.removeEventListener('contextmenu', handleContextMenu);
      document.removeEventListener('keydown', handleKeyDown);
      clearInterval(devToolsInterval);
    };
  }, [navigate, user]);

  return null;
};

function App() {
  return (
    <Router>
      <GlobalSecurity />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/queue/:eventId" element={<WaitingRoom />} />
        <Route path="/fairdrop-staff" element={<AdminLogin />} />
        <Route path="/fairdrop-staff/dashboard" element={<AdminDashboard />} />
        <Route path="/checkout/:eventId" element={<Checkout />} />
        <Route path="/bookings" element={<MyBookings />} />
      </Routes>
    </Router>
  );
}

export default App;
