import { HashRouter, Route, Routes, useLocation } from 'react-router-dom';
import TopNav from '@/components/TopNav';
import Footer from '@/components/Footer';
import Landing from '@/pages/Landing';
import Onboarding from '@/pages/Onboarding';
import Paper from '@/pages/Paper';
import PaperDetail from '@/pages/PaperDetail';
import Archive from '@/pages/Archive';
import Profile from '@/pages/Profile';

function PageTransition({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  return (
    <div key={location.pathname} className="animate-page">
      {children}
    </div>
  );
}

function AppRoutes() {
  return (
    <PageTransition>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/paper" element={<Paper />} />
        <Route path="/paper/:id" element={<PaperDetail />} />
        <Route path="/archive" element={<Archive />} />
        <Route path="/profile" element={<Profile />} />
      </Routes>
    </PageTransition>
  );
}

function App() {
  return (
    <HashRouter>
      <div className="flex min-h-screen flex-col bg-paper text-ink dark:bg-navy dark:text-cream-ink">
        <TopNav />
        <main className="flex-1">
          <AppRoutes />
        </main>
        <Footer />
      </div>
    </HashRouter>
  );
}

export default App;
