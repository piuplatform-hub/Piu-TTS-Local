import React from 'react';
import {
  LayoutDashboard,
  Mic2,
  Users2,
  Radio,
  BookOpen,
  History,
  Cpu,
  Settings,
  HardDrive,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react';
import { UserProfile } from '../../types';

export type NavItemKey =
  | 'projects'    // Dashboard / Dự Án Studio
  | 'speech'      // Speech Studio (Chuyển văn bản thành giọng nói)
  | 'dialogue'    // Dialogue Studio (Tạo hội thoại đa nhân vật)
  | 'voicelab'    // Voice Lab (Clone giọng nói, tùy chỉnh)
  | 'library'     // Thư viện (Giọng nói & tài nguyên)
  | 'history'     // Lịch sử tạo giọng
  | 'engines'     // Engines (Mô hình & cấu hình)
  | 'settings';   // Cài đặt hệ thống

interface AppSidebarProps {
  currentTab: NavItemKey;
  onSelectTab: (tab: NavItemKey) => void;
  user: UserProfile | null;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export const AppSidebar: React.FC<AppSidebarProps> = ({
  currentTab,
  onSelectTab,
  user,
  collapsed,
  onToggleCollapse,
}) => {
  const navItems = [
    {
      key: 'projects' as NavItemKey,
      label: 'Dự Án Studio',
      sublabel: 'Tổng quan dự án & Workstation',
      icon: LayoutDashboard,
      badge: null,
    },
    {
      key: 'speech' as NavItemKey,
      label: 'Speech Studio',
      sublabel: 'Chuyển văn bản thành giọng nói',
      icon: Mic2,
      badge: 'Chính',
    },
    {
      key: 'dialogue' as NavItemKey,
      label: 'Dialogue Studio',
      sublabel: 'Tạo hội thoại đa nhân vật',
      icon: Users2,
      badge: null,
    },
    {
      key: 'voicelab' as NavItemKey,
      label: 'Voice Lab',
      sublabel: 'Clone giọng nói, tùy chỉnh',
      icon: Radio,
      badge: null,
    },
    {
      key: 'library' as NavItemKey,
      label: 'Thư viện',
      sublabel: 'Giọng nói & tài nguyên',
      icon: BookOpen,
      badge: null,
    },
    {
      key: 'history' as NavItemKey,
      label: 'Lịch sử tạo giọng',
      sublabel: 'Các tệp đã tạo',
      icon: History,
      badge: null,
    },
    {
      key: 'engines' as NavItemKey,
      label: 'Engines',
      sublabel: 'Mô hình & cấu hình',
      icon: Cpu,
      badge: null,
    },
    {
      key: 'settings' as NavItemKey,
      label: 'Cài đặt',
      sublabel: 'Tài khoản & hệ thống',
      icon: Settings,
      badge: null,
    },
  ];

  return (
    <aside
      className={`relative flex flex-col border-r border-slate-800/80 bg-slate-950 text-slate-200 transition-all duration-200 z-30 select-none ${
        collapsed ? 'w-16' : 'w-60 xl:w-64'
      }`}
    >
      {/* Brand Logo & App Name */}
      <div className="flex h-14 items-center justify-between border-b border-slate-800/80 px-3.5">
        <div className="flex items-center space-x-2.5 overflow-hidden">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-teal-500/10 border border-teal-500/30 text-teal-400">
            <Mic2 className="h-4 w-4" />
          </div>
          {!collapsed && (
            <div className="flex flex-col truncate">
              <span className="text-sm font-semibold tracking-tight text-white flex items-center space-x-1.5">
                <span>AI Voice Studio</span>
              </span>
              <span className="text-[10px] font-medium text-slate-500 tracking-wide uppercase">
                Local-First Studio
              </span>
            </div>
          )}
        </div>

        {/* Toggle Collapse Button */}
        <button
          onClick={onToggleCollapse}
          className="flex h-6 w-6 items-center justify-center rounded-md text-slate-500 hover:bg-slate-900 hover:text-slate-300 transition-colors"
          title={collapsed ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>

      {/* Navigation Items List */}
      <nav className="flex-1 space-y-1 p-2 overflow-y-auto overflow-x-hidden">
        {navItems.map((item) => {
          const isActive = currentTab === item.key;
          const Icon = item.icon;

          return (
            <button
              key={item.key}
              onClick={() => onSelectTab(item.key)}
              title={collapsed ? item.label : undefined}
              className={`group flex w-full items-center rounded-lg px-2.5 py-2 text-left transition-all ${
                isActive
                  ? 'bg-teal-500/15 border border-teal-500/30 text-teal-300 font-medium'
                  : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200 border border-transparent'
              } ${collapsed ? 'justify-center px-0' : 'space-x-3'}`}
            >
              <Icon
                className={`h-4 w-4 shrink-0 transition-colors ${
                  isActive ? 'text-teal-400' : 'text-slate-400 group-hover:text-slate-300'
                }`}
              />
              {!collapsed && (
                <div className="flex flex-1 items-center justify-between truncate">
                  <div className="flex flex-col truncate">
                    <span className="text-xs leading-tight truncate">{item.label}</span>
                    <span className="text-[10px] leading-tight text-slate-500 truncate mt-0.5 group-hover:text-slate-400">
                      {item.sublabel}
                    </span>
                  </div>
                  {item.badge && (
                    <span className="ml-1.5 rounded bg-teal-500/20 px-1.5 py-0.5 text-[9px] font-medium text-teal-400 border border-teal-500/30">
                      {item.badge}
                    </span>
                  )}
                </div>
              )}
            </button>
          );
        })}
      </nav>

      {/* Real Local Storage & Host Status Card */}
      {!collapsed && (
        <div className="p-3 border-t border-slate-800/80">
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-2.5 text-xs space-y-2">
            <div className="flex items-center justify-between text-slate-400">
              <span className="flex items-center space-x-1.5 font-medium text-slate-300 text-[11px]">
                <HardDrive className="h-3.5 w-3.5 text-teal-400" />
                <span>Trạng thái Cục bộ</span>
              </span>
              <span className="inline-flex items-center px-1.5 py-0.2 rounded text-[9px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Local-First
              </span>
            </div>
            <div className="text-[10px] text-slate-400 space-y-1">
              <div className="flex justify-between">
                <span>Người dùng:</span>
                <span className="font-mono text-slate-200">{user?.username || 'Chưa đăng nhập'}</span>
              </div>
              <div className="flex justify-between">
                <span>Vai trò:</span>
                <span className="text-teal-300 uppercase font-medium">{user?.role || 'Guest'}</span>
              </div>
            </div>
            <div className="pt-1.5 border-t border-slate-800/80 flex items-center space-x-1.5 text-[10px] text-slate-500">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
              <span>Dữ liệu lưu 100% trên máy</span>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
};
