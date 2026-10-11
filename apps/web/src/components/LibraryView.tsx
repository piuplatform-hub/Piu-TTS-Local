import React, { useState, useEffect } from 'react';
import { Mic2, Plus, Calendar, Radio, RefreshCw } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { VoiceProfile } from '../types';

interface LibraryViewProps {
  onNavigateToVoiceLab: () => void;
}

export const LibraryView: React.FC<LibraryViewProps> = ({ onNavigateToVoiceLab }) => {
  const [profiles, setProfiles] = useState<VoiceProfile[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProfiles = async () => {
    try {
      setLoading(true);
      setError(null);
      const list = await api.listVoiceProfiles();
      setProfiles(list);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.problem.detail || err.message);
      } else {
        setError(err.message || 'Không thể tải danh sách hồ sơ giọng');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfiles();
  }, []);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white">Thư Viện Hồ Sơ Giọng Nói</h2>
          <p className="text-xs text-slate-400 mt-1">
            Quản lý các hồ sơ giọng đã nhân bản (Cloned Profiles) và tài nguyên âm thanh tham chiếu.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={fetchProfiles}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900 text-slate-300 hover:text-white hover:bg-slate-800 text-xs transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Làm mới</span>
          </button>
          <button
            onClick={onNavigateToVoiceLab}
            className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-xs font-medium shadow-sm transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Tạo Giọng Mới Tại Voice Lab</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
          {error}
        </div>
      )}

      {/* Profiles Grid */}
      {loading ? (
        <div className="text-center py-16 space-y-2">
          <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs text-slate-500">Đang tải danh sách hồ sơ giọng...</p>
        </div>
      ) : profiles.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/30 p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-xl bg-slate-800/80 flex items-center justify-center text-slate-400 mx-auto">
            <Mic2 className="h-6 w-6" />
          </div>
          <h3 className="text-sm font-semibold text-white">Chưa có hồ sơ giọng nào</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            Bạn có thể tải lên mẫu âm thanh tham chiếu 3s-10s trong Voice Lab để tạo hồ sơ giọng nhân bản đầu tiên.
          </p>
          <div className="pt-2">
            <button
              onClick={onNavigateToVoiceLab}
              className="inline-flex items-center space-x-1.5 px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-xs font-medium transition-colors"
            >
              <Radio className="h-3.5 w-3.5" />
              <span>Mở Voice Lab Ngay</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {profiles.map((profile) => (
            <div
              key={profile.id}
              className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 shadow-sm hover:border-slate-700 transition-all flex flex-col justify-between space-y-4"
            >
              <div className="space-y-2">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-white truncate">{profile.name}</h3>
                    <span className="inline-block mt-0.5 text-[10px] font-mono px-2 py-0.5 rounded-full bg-teal-500/10 text-teal-400 border border-teal-500/20">
                      {profile.engine_id}
                    </span>
                  </div>
                  <div className="h-8 w-8 rounded-lg bg-slate-800/80 flex items-center justify-center text-teal-400">
                    <Mic2 className="h-4 w-4" />
                  </div>
                </div>

                {profile.description && (
                  <p className="text-xs text-slate-400 line-clamp-2">{profile.description}</p>
                )}
              </div>

              <div className="border-t border-slate-800/60 pt-3 space-y-2 text-[11px] text-slate-400">
                <div className="flex items-center justify-between">
                  <span className="flex items-center space-x-1">
                    <Calendar className="h-3 w-3" />
                    <span>{new Date(profile.created_at).toLocaleDateString()}</span>
                  </span>
                  <span className="font-mono text-[10px] text-slate-500">
                    {profile.reference_asset_id ? 'Có mẫu Clone' : 'Không có mẫu'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
