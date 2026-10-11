import React from 'react';
import { ShieldCheck, Cpu, Sliders, KeyRound, CheckCircle2 } from 'lucide-react';
import { UserProfile } from '../types';

interface SettingsViewProps {
  user: UserProfile;
}

export const SettingsView: React.FC<SettingsViewProps> = ({ user }) => {
  return (
    <div className="space-y-6 max-w-[1680px] mx-auto select-none">
      {/* Page Header */}
      <div className="pb-4 border-b border-slate-800/80">
        <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">Cài Đặt Hệ Thống</h2>
        <p className="text-xs text-slate-400 mt-1">
          Quản lý tài khoản cục bộ, kiến trúc phân phối bảo mật và thông số âm thanh chuẩn.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* User Account Details */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-sm space-y-4">
          <div className="flex items-center space-x-3 border-b border-slate-800/80 pb-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <KeyRound className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Tài Khoản Phiên Làm Việc</h3>
              <p className="text-[11px] text-slate-400">Thông tin xác thực phiên làm việc cục bộ</p>
            </div>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between items-center py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Tên người dùng</span>
              <span className="font-mono font-medium text-slate-200">{user.username}</span>
            </div>
            <div className="flex justify-between items-center py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Vai trò ủy quyền</span>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono uppercase bg-teal-500/10 text-teal-400 border border-teal-500/20">
                {user.role}
              </span>
            </div>
            <div className="flex justify-between items-center py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Trạng thái bảo mật</span>
              <span className="inline-flex items-center space-x-1 text-emerald-400 font-medium text-[11px]">
                <CheckCircle2 className="h-3 w-3" />
                <span>Hoạt động (Active)</span>
              </span>
            </div>
            <div className="flex justify-between items-center py-1.5">
              <span className="text-slate-400">Mã định danh (UID)</span>
              <span className="font-mono text-slate-400 text-[10px] truncate max-w-[200px]">{user.id}</span>
            </div>
          </div>
        </div>

        {/* Local-First Architecture */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-sm space-y-4">
          <div className="flex items-center space-x-3 border-b border-slate-800/80 pb-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Kiến Trúc Local-First</h3>
              <p className="text-[11px] text-slate-400">Cách ly hoàn toàn mạng nội bộ & máy khách</p>
            </div>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between items-center py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Địa chỉ lắng nghe</span>
              <span className="font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded text-[11px]">
                127.0.0.1 (Loopback Only)
              </span>
            </div>
            <div className="flex justify-between items-center py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Cổng dịch vụ chính</span>
              <span className="font-mono text-slate-200">TCP 8765 / 8769</span>
            </div>
            <div className="flex justify-between items-center py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Chế độ tường lửa</span>
              <span className="text-slate-300">Không mở cổng LAN bên ngoài</span>
            </div>
            <div className="flex justify-between items-center py-1.5">
              <span className="text-slate-400">Cơ sở dữ liệu</span>
              <span className="font-mono text-slate-300 text-[11px]">SQLite WAL Cục Bộ</span>
            </div>
          </div>
        </div>

        {/* Audio Engine Configuration */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-sm space-y-4">
          <div className="flex items-center space-x-3 border-b border-slate-800/80 pb-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <Cpu className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Động Cơ Tổng Hợp Giọng Nói</h3>
              <p className="text-[11px] text-slate-400">Các mô hình AI được nạp vào bộ nhớ</p>
            </div>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between items-center py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Mô hình tiếng Việt chính</span>
              <span className="font-semibold text-teal-400">VieNeu-TTS (V3 Turbo)</span>
            </div>
            <div className="flex justify-between items-center py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Tần số lấy mẫu mặc định</span>
              <span className="font-mono text-slate-200">48,000 Hz / 24,000 Hz</span>
            </div>
            <div className="flex justify-between items-center py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Độ sâu lượng tử</span>
              <span className="text-slate-200">16-bit PCM Linear</span>
            </div>
            <div className="flex justify-between items-center py-1.5">
              <span className="text-slate-400">Hàng đợi bền vững</span>
              <span className="text-emerald-400">Durable SQLite Queue</span>
            </div>
          </div>
        </div>

        {/* System & Audio Mastering Defaults */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-sm space-y-4">
          <div className="flex items-center space-x-3 border-b border-slate-800/80 pb-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <Sliders className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Hậu Kỳ Âm Thanh Chuẩn</h3>
              <p className="text-[11px] text-slate-400">Xử lý tín hiệu FFmpeg DSP & EBU R128</p>
            </div>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between items-center py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Chuẩn âm lượng phát sóng</span>
              <span className="font-mono text-slate-200">EBU R128 (-16 LUFS)</span>
            </div>
            <div className="flex justify-between items-center py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Ngưỡng đỉnh thực tế (True Peak)</span>
              <span className="font-mono text-slate-200">-1.0 dBTP</span>
            </div>
            <div className="flex justify-between items-center py-1.5 border-b border-slate-800/40">
              <span className="text-slate-400">Bộ lọc thông cao (High-pass)</span>
              <span className="font-mono text-slate-200">50 Hz Butterworth</span>
            </div>
            <div className="flex justify-between items-center py-1.5">
              <span className="text-slate-400">Phiên bản giao diện</span>
              <span className="font-mono text-teal-400">v1.2.0 Modern Studio</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
