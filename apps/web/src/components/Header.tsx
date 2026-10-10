import React from 'react';
import { Mic2, User, LogOut, Radio, History, Cpu, Layers } from 'lucide-react';
import { UserProfile } from '../types';

export type AppTabType = 'projects' | 'single' | 'history' | 'engines';

interface HeaderProps {
  user: UserProfile | null;
  activeTab: AppTabType;
  onTabChange: (tab: AppTabType) => void;
  onLogout: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  user,
  activeTab,
  onTabChange,
  onLogout,
}) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-purple-600 via-emerald-600 to-teal-500 flex items-center justify-center shadow-lg shadow-purple-950/40">
            <Mic2 className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-lg text-white tracking-tight">AI Voice Studio</span>
              <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Phase 6A Voice Lab
              </span>
            </div>
            <p className="text-xs text-slate-400">Local-First Multi-Speaker Speech Workstation</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        {user && (
          <nav className="flex items-center space-x-1 bg-slate-950/60 p-1 rounded-xl border border-slate-800/80">
            <button
              onClick={() => onTabChange('projects')}
              className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'projects'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Dự Án Studio</span>
            </button>
            <button
              onClick={() => onTabChange('single')}
              className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'single'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Radio className="w-3.5 h-3.5" />
              <span>Voice Lab</span>
            </button>
            <button
              onClick={() => onTabChange('history')}
              className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'history'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <History className="w-3.5 h-3.5" />
              <span>Lịch sử</span>
            </button>
            <button
              onClick={() => onTabChange('engines')}
              className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeTab === 'engines'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Cpu className="w-3.5 h-3.5" />
              <span>Engines</span>
            </button>
          </nav>
        )}

        {/* User Info & Actions */}
        {user && (
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-800/50 border border-slate-700/60">
              <User className="w-4 h-4 text-emerald-400" />
              <div className="text-left">
                <span className="text-xs font-medium text-slate-200 block">{user.username}</span>
                <span className="text-[10px] text-emerald-400 font-mono uppercase">{user.role}</span>
              </div>
            </div>
            <button
              onClick={onLogout}
              title="Đăng xuất"
              className="p-2 rounded-lg bg-slate-800/40 hover:bg-red-500/10 text-slate-400 hover:text-red-400 border border-slate-700/50 hover:border-red-500/20 transition-all"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
};
