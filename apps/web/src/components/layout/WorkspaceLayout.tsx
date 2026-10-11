import React, { useState } from 'react';
import { AppSidebar, NavItemKey } from './AppSidebar';
import { AppHeader } from './AppHeader';
import { UserProfile, EngineInfo } from '../../types';

interface WorkspaceLayoutProps {
  currentTab: NavItemKey;
  onSelectTab: (tab: NavItemKey) => void;
  user: UserProfile | null;
  onLogout: () => void;
  activeProjectTitle?: string | null;
  onClearActiveProject?: () => void;
  activeEngine?: EngineInfo | null;
  children: React.ReactNode;
}

export const WorkspaceLayout: React.FC<WorkspaceLayoutProps> = ({
  currentTab,
  onSelectTab,
  user,
  onLogout,
  activeProjectTitle,
  onClearActiveProject,
  activeEngine,
  children,
}) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [showHelpModal, setShowHelpModal] = useState(false);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 font-sans text-slate-100 antialiased selection:bg-teal-500/30 selection:text-teal-200">
      {/* Collapsible Left Sidebar */}
      <AppSidebar
        currentTab={currentTab}
        onSelectTab={onSelectTab}
        user={user}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Content Workspace Column */}
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <AppHeader
          user={user}
          activeProjectTitle={activeProjectTitle}
          onClearActiveProject={onClearActiveProject}
          activeEngine={activeEngine}
          onLogout={onLogout}
          onOpenHelp={() => setShowHelpModal(true)}
        />

        {/* Dynamic Page Workspace Body */}
        <main className="flex-1 overflow-y-auto min-w-0 bg-slate-950/60 p-4 lg:p-6 space-y-6">
          {children}
        </main>
      </div>

      {/* Quick Help & Shortcuts Modal */}
      {showHelpModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-semibold text-white">Hướng Dẫn & Phím Tắt Hệ Thống</h3>
              <button
                onClick={() => setShowHelpModal(false)}
                className="text-slate-400 hover:text-white text-xs px-1.5 py-0.5 rounded"
              >
                ✕
              </button>
            </div>
            <div className="space-y-2.5 text-xs text-slate-300">
              <div className="flex justify-between items-center py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Tạo giọng nói AI</span>
                <kbd className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[11px] text-teal-300 border border-slate-700">
                  Ctrl + Enter
                </kbd>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Xóa trắng nội dung văn bản</span>
                <kbd className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[11px] text-slate-300 border border-slate-700">
                  Ctrl + Shift + X
                </kbd>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Thời lượng mẫu Clone khuyến nghị</span>
                <span className="font-mono text-teal-400 font-medium">3s - 10s WAV (PCM)</span>
              </div>
              <div className="flex justify-between items-center py-1">
                <span className="text-slate-400">Tần số mẫu chuẩn đầu ra</span>
                <span className="font-mono text-emerald-400 font-medium">48,000 Hz / 16-bit PCM</span>
              </div>
            </div>
            <div className="pt-2">
              <button
                onClick={() => setShowHelpModal(false)}
                className="w-full rounded-lg bg-slate-800 py-2 text-xs font-medium text-slate-200 hover:bg-slate-700 transition-colors"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
