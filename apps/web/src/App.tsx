import React, { useState, useEffect } from 'react';
import { api } from './api/client';
import { UserProfile, AuthResponse } from './types';
import { Header } from './components/Header';
import { OnboardingModal } from './components/OnboardingModal';
import { LoginForm } from './components/LoginForm';
import { StudioView } from './components/StudioView';
import { JobHistoryTable } from './components/JobHistoryTable';
import { EngineStatusCard } from './components/EngineStatusCard';

export const App: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [activeTab, setActiveTab] = useState<'studio' | 'history' | 'engines'>('studio');

  const checkInitialState = async () => {
    try {
      setLoading(true);
      const status = await api.getAuthStatus();

      if (status.needs_onboarding) {
        setNeedsOnboarding(true);
        setUser(null);
        return;
      }

      setNeedsOnboarding(false);

      if (api.getToken()) {
        try {
          const profile = await api.getMe();
          setUser(profile);
        } catch {
          api.clearToken();
          setUser(null);
        }
      }
    } catch (err) {
      console.error('Failed to query initial auth status', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkInitialState();
  }, []);

  const handleAuthSuccess = (auth: AuthResponse) => {
    setUser(auth.user);
    setNeedsOnboarding(false);
    setActiveTab('studio');
  };

  const handleLogout = () => {
    api.clearToken();
    setUser(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center space-y-4">
        <div className="w-10 h-10 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-slate-400">Đang khởi tạo AI Voice Studio...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Onboarding Overlay */}
      {needsOnboarding && (
        <OnboardingModal onSuccess={handleAuthSuccess} />
      )}

      {/* Login Screen if onboarding completed but unauthenticated */}
      {!needsOnboarding && !user && (
        <div className="flex-1 flex flex-col">
          <Header
            user={null}
            activeTab="studio"
            onTabChange={() => {}}
            onLogout={() => {}}
          />
          <main className="flex-1">
            <LoginForm onSuccess={handleAuthSuccess} />
          </main>
        </div>
      )}

      {/* Main Authenticated Studio Application */}
      {!needsOnboarding && user && (
        <div className="flex-1 flex flex-col">
          <Header
            user={user}
            activeTab={activeTab}
            onTabChange={setActiveTab}
            onLogout={handleLogout}
          />

          <main className="flex-1">
            {activeTab === 'studio' && <StudioView />}
            {activeTab === 'history' && <JobHistoryTable />}
            {activeTab === 'engines' && <EngineStatusCard />}
          </main>

          <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-500">
            <p>
              AI Voice Studio Phase 1 • Local-First Architecture • SQLite WAL Engine • Isolated Worker Processes
            </p>
          </footer>
        </div>
      )}
    </div>
  );
};

export default App;
