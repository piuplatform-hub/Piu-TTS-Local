import React from 'react';
import {
  Layers,
  FolderGit2,
  LogOut,
  Radio,
  Cpu,
  User,
  Shield,
  HelpCircle,
} from 'lucide-react';
import { UserProfile, EngineInfo } from '../../types';

interface AppHeaderProps {
  user: UserProfile | null;
  activeProjectTitle?: string | null;
  onClearActiveProject?: () => void;
  activeEngine?: EngineInfo | null;
  onLogout: () => void;
  onOpenHelp?: () => void;
}

export const AppHeader: React.FC<AppHeaderProps> = ({
  user,
  activeProjectTitle,
  onClearActiveProject,
  activeEngine,
  onLogout,
  onOpenHelp,
}) => {
  const engineVersion = activeEngine?.version || 'v3.8.3';
  const engineSampleRate = activeEngine?.id === 'qwen3-tts' ? '24kHz' : '48kHz';

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-md px-4 select-none">
      {/* Left: Workspace & Active Project Breadcrumbs */}
      <div className="flex items-center space-x-3 text-xs overflow-hidden">
        {/* Workspace selector badge */}
        <div className="flex items-center space-x-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1 text-slate-300">
          <Layers className="h-3.5 w-3.5 text-teal-400" />
          <span className="font-medium">Workspace:</span>
          <span className="text-slate-100">Default Workspace</span>
        </div>

        {/* Current Active Project (if loaded) */}
        {activeProjectTitle ? (
          <div className="flex items-center space-x-1.5 rounded-lg border border-teal-500/30 bg-teal-500/10 px-2.5 py-1 text-teal-300 truncate max-w-xs">
            <FolderGit2 className="h-3.5 w-3.5 text-teal-400 shrink-0" />
            <span className="text-slate-400">Dự án:</span>
            <span className="font-medium text-teal-200 truncate">{activeProjectTitle}</span>
            {onClearActiveProject && (
              <button
                onClick={onClearActiveProject}
                className="ml-1 text-[10px] text-slate-400 hover:text-white"
                title="Đóng dự án hiện tại"
              >
                ✕
              </button>
            )}
          </div>
        ) : null}
      </div>

      {/* Right: Technical Badges, Help & User Profile */}
      <div className="flex items-center space-x-2 text-xs">
        {/* Local-first Badge */}
        <span className="hidden sm:inline-flex items-center space-x-1 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>Local-first</span>
        </span>

        {/* Engine Spec Badges */}
        <span className="hidden md:inline-flex items-center space-x-1 rounded-full border border-slate-800 bg-slate-900 px-2 py-0.5 text-[11px] font-mono text-slate-300">
          <Radio className="h-3 w-3 text-teal-400" />
          <span>{engineVersion}</span>
        </span>

        <span className="hidden md:inline-flex items-center space-x-1 rounded-full border border-slate-800 bg-slate-900 px-2 py-0.5 text-[11px] font-mono text-slate-300">
          <Cpu className="h-3 w-3 text-teal-400" />
          <span>{engineSampleRate}</span>
        </span>

        {/* Help guide button */}
        {onOpenHelp && (
          <button
            onClick={onOpenHelp}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-900 hover:text-slate-200 transition-colors"
            title="Hướng dẫn & Phím tắt"
          >
            <HelpCircle className="h-4 w-4" />
          </button>
        )}

        {/* User Profile Pill */}
        {user ? (
          <div className="flex items-center space-x-2 pl-2 border-l border-slate-800">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-teal-600/30 border border-teal-500/40 text-teal-300 font-semibold text-xs">
              {user.username.charAt(0).toUpperCase()}
            </div>
            <div className="hidden lg:flex flex-col text-left leading-tight">
              <span className="font-medium text-slate-200 truncate max-w-[120px]">{user.username}</span>
              <span className="text-[10px] text-slate-500 uppercase flex items-center space-x-1">
                {user.role === 'admin' ? (
                  <Shield className="h-2.5 w-2.5 text-amber-400" />
                ) : (
                  <User className="h-2.5 w-2.5 text-slate-400" />
                )}
                <span>{user.role}</span>
              </span>
            </div>
            <button
              onClick={onLogout}
              className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-red-500/10 hover:text-red-400 transition-colors"
              title="Đăng xuất"
            >
              <LogOut className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
};
