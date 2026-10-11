import React, { useState, useEffect } from 'react';
import { Mic2, Plus, Calendar, Radio, RefreshCw, Search, Trash2, Play, Volume2, Sliders } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { VoiceProfile } from '../types';

interface LibraryViewProps {
  onNavigateToVoiceLab: () => void;
}

export const LibraryView: React.FC<LibraryViewProps> = ({ onNavigateToVoiceLab }) => {
  const [profiles, setProfiles] = useState<VoiceProfile[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [sortBy, setSortBy] = useState<'newest' | 'oldest' | 'name'>('newest');
  const [playingAssetId, setPlayingAssetId] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

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

  const handleDelete = async (profileId: string, name: string) => {
    if (!window.confirm(`Bạn có chắc muốn xóa hồ sơ giọng "${name}"?`)) return;
    try {
      await api.deleteVoiceProfile(profileId);
      setProfiles((prev) => prev.filter((p) => p.id !== profileId));
    } catch (err: any) {
      setError(err.message || 'Lỗi khi xóa hồ sơ giọng.');
    }
  };

  const handlePlayAsset = async (assetId: string) => {
    try {
      if (playingAssetId === assetId && audioUrl) {
        URL.revokeObjectURL(audioUrl);
        setPlayingAssetId(null);
        setAudioUrl(null);
        return;
      }
      const blob = await api.fetchReferenceAudioBlob(assetId);
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
      const url = URL.createObjectURL(blob);
      setPlayingAssetId(assetId);
      setAudioUrl(url);
    } catch (err: any) {
      setError('Không thể phát tệp âm thanh tham chiếu.');
    }
  };

  const filteredProfiles = profiles
    .filter((p) => {
      const q = searchQuery.toLowerCase().trim();
      if (!q) return true;
      return (
        p.name.toLowerCase().includes(q) ||
        (p.description && p.description.toLowerCase().includes(q)) ||
        p.engine_id.toLowerCase().includes(q)
      );
    })
    .sort((a, b) => {
      if (sortBy === 'name') {
        return a.name.localeCompare(b.name);
      }
      if (sortBy === 'oldest') {
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });

  return (
    <div className="space-y-6 max-w-[1680px] mx-auto select-none">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white flex items-center space-x-2.5">
            <span>Thư Viện Hồ Sơ Giọng Nói</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-teal-500/10 text-teal-300 border border-teal-500/20 font-mono">
              {profiles.length} Hồ sơ
            </span>
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Quản lý các hồ sơ giọng đã nhân bản (Cloned Profiles) và tài nguyên âm thanh tham chiếu cục bộ.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={fetchProfiles}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3 py-2 rounded-xl border border-slate-800 bg-slate-900 text-slate-300 hover:text-white hover:bg-slate-800 text-xs transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Làm mới</span>
          </button>
          <button
            onClick={onNavigateToVoiceLab}
            className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold shadow-sm transition-colors"
          >
            <Plus className="h-4 w-4" />
            <span>Tạo Giọng Mới Tại Voice Lab</span>
          </button>
        </div>
      </div>

      {/* Search and Sort Toolbar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-2xl border border-slate-800">
        <div className="relative flex-1 max-w-md">
          <Search className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm kiếm theo tên hồ sơ, mô tả hoặc engine..."
            className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-teal-500 transition-colors"
          />
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-xs text-slate-400">Sắp xếp:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="bg-slate-950 border border-slate-800 text-xs text-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:border-teal-500 font-medium"
          >
            <option value="newest">Mới nhất trước</option>
            <option value="oldest">Cũ nhất trước</option>
            <option value="name">Tên (A-Z)</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs">
          {error}
        </div>
      )}

      {/* Playing Preview Bar if active */}
      {playingAssetId && audioUrl && (
        <div className="p-3 bg-teal-950/40 border border-teal-500/30 rounded-xl flex items-center justify-between gap-3">
          <div className="flex items-center space-x-2 text-xs text-teal-300 font-medium truncate">
            <Volume2 className="h-4 w-4 text-teal-400 shrink-0" />
            <span className="truncate">Đang phát mẫu tham chiếu ID: {playingAssetId}</span>
          </div>
          <audio autoPlay controls src={audioUrl} className="h-8 w-64 shrink-0" />
        </div>
      )}

      {/* Profiles Grid */}
      {loading ? (
        <div className="text-center py-20 space-y-2">
          <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs text-slate-400">Đang tải danh sách hồ sơ giọng...</p>
        </div>
      ) : filteredProfiles.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-900/40 p-16 text-center space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-slate-800/80 flex items-center justify-center text-slate-400 mx-auto">
            <Mic2 className="h-6 w-6 text-teal-400" />
          </div>
          <h3 className="text-sm font-bold text-white">
            {searchQuery ? 'Không tìm thấy hồ sơ phù hợp' : 'Chưa có hồ sơ giọng nào'}
          </h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto leading-relaxed">
            {searchQuery
              ? 'Thử thay đổi từ khóa tìm kiếm hoặc xóa bộ lọc để hiển thị toàn bộ hồ sơ.'
              : 'Bạn có thể tải lên mẫu âm thanh tham chiếu 3s-10s trong Voice Lab để tạo hồ sơ giọng nhân bản đầu tiên.'}
          </p>
          <div className="pt-2">
            <button
              onClick={onNavigateToVoiceLab}
              className="inline-flex items-center space-x-1.5 px-4 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold transition-colors"
            >
              <Radio className="h-4 w-4" />
              <span>Mở Voice Lab Ngay</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredProfiles.map((profile) => (
            <div
              key={profile.id}
              className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-sm hover:border-slate-700 hover:bg-slate-900 transition-all flex flex-col justify-between space-y-4"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <h3 className="text-sm font-bold text-white truncate max-w-[220px]">{profile.name}</h3>
                    <span className="inline-block text-[11px] font-mono px-2 py-0.5 rounded-full bg-teal-500/10 text-teal-300 border border-teal-500/20">
                      {profile.engine_id}
                    </span>
                  </div>
                  <div className="h-9 w-9 rounded-xl bg-slate-800/80 flex items-center justify-center text-teal-400 border border-slate-700/60">
                    <Mic2 className="h-4 w-4" />
                  </div>
                </div>

                {profile.description ? (
                  <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">{profile.description}</p>
                ) : (
                  <p className="text-xs text-slate-500 italic">Chưa có ghi chú mô tả</p>
                )}

                {/* Parameters Preview if present */}
                {profile.parameters && (
                  <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 text-[11px] text-slate-300 space-y-1">
                    <div className="flex justify-between items-center">
                      <span className="text-slate-400 flex items-center space-x-1">
                        <Sliders className="h-3 w-3 text-teal-400" />
                        <span>Tốc độ:</span>
                      </span>
                      <span className="font-mono text-teal-300">{profile.parameters.speed ?? 1.0}x</span>
                    </div>
                    {profile.parameters.temperature !== undefined && (
                      <div className="flex justify-between items-center">
                        <span className="text-slate-400">Độ biến thiên (Temp):</span>
                        <span className="font-mono text-teal-300">{profile.parameters.temperature}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="border-t border-slate-800/80 pt-3 space-y-3">
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span className="flex items-center space-x-1">
                    <Calendar className="h-3 w-3" />
                    <span>{new Date(profile.created_at).toLocaleDateString()}</span>
                  </span>
                  <span className={`font-mono text-[10px] px-2 py-0.5 rounded ${
                    profile.reference_asset_id
                      ? 'bg-teal-500/10 text-teal-400'
                      : 'bg-slate-800 text-slate-500'
                  }`}>
                    {profile.reference_asset_id ? 'Có mẫu WAV' : 'Không có mẫu'}
                  </span>
                </div>

                <div className="flex items-center justify-between pt-1 gap-2">
                  <div className="flex items-center space-x-1">
                    {profile.reference_asset_id && (
                      <button
                        type="button"
                        onClick={() => handlePlayAsset(profile.reference_asset_id)}
                        className="px-2.5 py-1.5 rounded-lg border border-slate-700 bg-slate-800/60 hover:bg-slate-800 text-slate-300 hover:text-white text-xs font-medium flex items-center space-x-1 transition-colors"
                        title="Nghe thử mẫu WAV gốc"
                      >
                        <Play className="h-3 w-3 text-teal-400" />
                        <span>Nghe mẫu</span>
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleDelete(profile.id, profile.name)}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-slate-800 transition-colors"
                      title="Xóa hồ sơ giọng"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={onNavigateToVoiceLab}
                    className="px-3 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold shadow-sm transition-colors"
                  >
                    Dùng tại Voice Lab
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

