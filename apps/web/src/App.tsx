import React, { useState, useEffect } from 'react';
import { api } from './api/client';
import { UserProfile, AuthResponse, EngineInfo } from './types';
import { Header } from './components/Header';
import { OnboardingModal } from './components/OnboardingModal';
import { LoginForm } from './components/LoginForm';
import { ProjectsView } from './components/ProjectsView';
import { SpeechStudioView } from './components/SpeechStudioView';
import { DialogueStudioView } from './components/DialogueStudioView';
import { StudioView } from './components/StudioView';
import { JobHistoryTable } from './components/JobHistoryTable';
import { EngineStatusCard } from './components/EngineStatusCard';
import { WorkspaceLayout } from './components/layout/WorkspaceLayout';
import { NavItemKey } from './components/layout/AppSidebar';
import { ModernSpeechStudio } from './components/ModernSpeechStudio';
import { SettingsView } from './components/SettingsView';
import { LibraryView } from './components/LibraryView';

export const App: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [activeTab, setActiveTab] = useState<NavItemKey>('projects');
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [selectedProjectType, setSelectedProjectType] = useState<'narration' | 'dialogue' | null>(null);
  const [activeEngine, setActiveEngine] = useState<EngineInfo | null>(null);

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
          // Try fetching active engine
          try {
            const engines = await api.getEngines();
            const primary = engines.find((e) => e.approval_status === 'approved') || engines[0] || null;
            setActiveEngine(primary);
          } catch {
            // Engine fetch is non-blocking
          }
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

  const handleAuthSuccess = async (auth: AuthResponse) => {
    setUser(auth.user);
    setNeedsOnboarding(false);
    setActiveTab('projects');
    try {
      const engines = await api.getEngines();
      const primary = engines.find((e) => e.approval_status === 'approved') || engines[0] || null;
      setActiveEngine(primary);
    } catch {
      // non-blocking
    }
  };

  const handleLogout = () => {
    api.clearToken();
    setUser(null);
    setSelectedProjectId(null);
    setSelectedProjectType(null);
  };

  const handleSelectProject = (projectId: string, projectType: 'narration' | 'dialogue') => {
    setSelectedProjectId(projectId);
    setSelectedProjectType(projectType);
    setActiveTab('projects');
  };

  const handleBackToProjects = () => {
    setSelectedProjectId(null);
    setSelectedProjectType(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center space-y-4">
        <div className="w-9 h-9 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
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
            activeTab="projects"
            onTabChange={() => {}}
            onLogout={() => {}}
          />
          <main className="flex-1 flex items-center justify-center p-4">
            <LoginForm onSuccess={handleAuthSuccess} />
          </main>
        </div>
      )}

      {/* Main Authenticated Modern Studio Workspace */}
      {!needsOnboarding && user && (
        <WorkspaceLayout
          currentTab={activeTab}
          onSelectTab={(tab) => {
            setActiveTab(tab);
          }}
          user={user}
          onLogout={handleLogout}
          activeProjectTitle={selectedProjectId ? (selectedProjectType === 'dialogue' ? 'Kịch bản đối thoại' : 'Sách nói tường thuật') : null}
          onClearActiveProject={handleBackToProjects}
          activeEngine={activeEngine}
        >
          {activeTab === 'projects' && (
            selectedProjectId ? (
              selectedProjectType === 'dialogue' ? (
                <DialogueStudioView
                  projectId={selectedProjectId}
                  onBack={handleBackToProjects}
                />
              ) : (
                <SpeechStudioView
                  projectId={selectedProjectId}
                  onBack={handleBackToProjects}
                />
              )
            ) : (
              <ProjectsView onSelectProject={handleSelectProject} />
            )
          )}

          {activeTab === 'speech' && (
            <ModernSpeechStudio />
          )}

          {activeTab === 'dialogue' && (
            selectedProjectId && selectedProjectType === 'dialogue' ? (
              <DialogueStudioView
                projectId={selectedProjectId}
                onBack={handleBackToProjects}
              />
            ) : (
              <ProjectsView onSelectProject={handleSelectProject} />
            )
          )}

          {activeTab === 'voicelab' && (
            <StudioView />
          )}

          {activeTab === 'library' && (
            <LibraryView onNavigateToVoiceLab={() => setActiveTab('voicelab')} />
          )}

          {activeTab === 'history' && (
            <JobHistoryTable />
          )}

          {activeTab === 'engines' && (
            <EngineStatusCard />
          )}

          {activeTab === 'settings' && (
            <SettingsView user={user} />
          )}
        </WorkspaceLayout>
      )}
    </div>
  );
};

export default App;
