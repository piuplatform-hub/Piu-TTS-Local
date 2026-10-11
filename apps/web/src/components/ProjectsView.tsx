import React, { useState, useEffect } from 'react';
import {
  FolderPlus,
  BookOpen,
  Users,
  Clock,
  Music,
  Trash2,
  ExternalLink,
  RefreshCw,
  Search,
  CheckCircle2,
  Layers,
} from 'lucide-react';
import { api, ApiError } from '../api/client';
import { ProjectSummary } from '../types';

interface ProjectsViewProps {
  onSelectProject: (projectId: string, projectType: 'narration' | 'dialogue') => void;
}

export const ProjectsView: React.FC<ProjectsViewProps> = ({ onSelectProject }) => {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [filterType, setFilterType] = useState<'all' | 'narration' | 'dialogue'>('all');
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [newTitle, setNewTitle] = useState<string>('');
  const [newDescription, setNewDescription] = useState<string>('');
  const [newType, setNewType] = useState<'narration' | 'dialogue'>('narration');
  const [creating, setCreating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      setError(null);
      const list = await api.listProjects();
      setProjects(list);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.problem.detail || err.message);
      } else {
        setError(err.message || 'Không thể tải danh sách dự án');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;

    try {
      setCreating(true);
      setError(null);
      const created = await api.createProject({
        title: newTitle.trim(),
        description: newDescription.trim() || undefined,
        project_type: newType,
      });
      setIsCreateOpen(false);
      setNewTitle('');
      setNewDescription('');
      setNewType('narration');
      await fetchProjects();
      // Chuyển thẳng vào project mới tạo
      onSelectProject(created.id, created.project_type);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.problem.detail || err.message);
      } else {
        setError(err.message || 'Không thể tạo dự án');
      }
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (p: ProjectSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm(`Bạn có chắc chắn muốn xóa dự án "${p.title}" không? Hành động này không thể hoàn tác.`)) {
      return;
    }

    try {
      await api.deleteProject(p.id);
      setProjects(prev => prev.filter(item => item.id !== p.id));
    } catch (err: any) {
      alert(`Xóa dự án thất bại: ${err.message}`);
    }
  };

  const filteredProjects = projects.filter(p => {
    const matchesSearch = p.title.toLowerCase().includes(search.toLowerCase()) ||
      (p.description && p.description.toLowerCase().includes(search.toLowerCase()));
    const matchesType = filterType === 'all' || p.project_type === filterType;
    return matchesSearch && matchesType;
  });

  return (
    <div className="space-y-6 max-w-[1680px] mx-auto select-none">
      {/* Top Banner & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-800/80">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white flex items-center space-x-3">
            <span className="p-2 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <Layers className="w-5 h-5" />
            </span>
            <span>Không Gian Làm Việc Dự Án (Workstation)</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Quản lý các dự án sách nói dài tập (Long-form Narration) và kịch truyền thanh nhiều nhân vật (Dialogue Studio)
          </p>
        </div>

        <button
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-teal-950/40 transition-all self-start sm:self-auto"
        >
          <FolderPlus className="w-4 h-4" />
          <span>Tạo Dự Án Mới</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Tìm kiếm dự án theo tiêu đề..."
            className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-teal-500 transition-colors"
          />
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-xs text-slate-400">Bộ lọc:</span>
          <div className="flex bg-slate-900 p-1 rounded-xl border border-slate-800 text-xs">
            <button
              onClick={() => setFilterType('all')}
              className={`px-3 py-1 rounded-lg transition-colors ${
                filterType === 'all' ? 'bg-teal-600 text-white font-medium' : 'text-slate-400 hover:text-white'
              }`}
            >
              Tất cả ({projects.length})
            </button>
            <button
              onClick={() => setFilterType('narration')}
              className={`px-3 py-1 rounded-lg transition-colors ${
                filterType === 'narration' ? 'bg-teal-600 text-white font-medium' : 'text-slate-400 hover:text-white'
              }`}
            >
              Sách nói ({projects.filter(p => p.project_type === 'narration').length})
            </button>
            <button
              onClick={() => setFilterType('dialogue')}
              className={`px-3 py-1 rounded-lg transition-colors ${
                filterType === 'dialogue' ? 'bg-teal-600 text-white font-medium' : 'text-slate-400 hover:text-white'
              }`}
            >
              Hội thoại ({projects.filter(p => p.project_type === 'dialogue').length})
            </button>
          </div>

          <button
            onClick={fetchProjects}
            title="Làm mới danh sách"
            className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-purple-400' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs">
          {error}
        </div>
      )}

      {/* Projects Grid */}
      {loading && projects.length === 0 ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3">
          <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-slate-400">Đang tải danh sách dự án...</p>
        </div>
      ) : filteredProjects.length === 0 ? (
        <div className="p-12 text-center border border-dashed border-slate-800 rounded-2xl bg-slate-900/40 space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-slate-800 text-slate-500 flex items-center justify-center mx-auto">
            <BookOpen className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-semibold text-slate-300">Chưa có dự án nào</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Bắt đầu sáng tạo bằng cách bấm &quot;Tạo Dự Án Mới&quot; để thiết lập kịch bản sách nói hoặc phim kịch hội thoại.
          </p>
          <button
            onClick={() => setIsCreateOpen(true)}
            className="inline-flex items-center space-x-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-xs font-semibold shadow-md transition-colors"
          >
            <FolderPlus className="w-4 h-4" />
            <span>Tạo dự án đầu tiên</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredProjects.map(p => {
            const isNarration = p.project_type === 'narration';
            const progress = p.segment_count > 0 ? Math.round((p.completed_segment_count / p.segment_count) * 100) : 0;

            return (
              <div
                key={p.id}
                onClick={() => onSelectProject(p.id, p.project_type)}
                className="group p-5 rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-purple-500/50 hover:bg-slate-900 transition-all cursor-pointer shadow-lg hover:shadow-purple-950/20 flex flex-col justify-between space-y-4"
              >
                <div className="space-y-3">
                  {/* Card Header */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center space-x-2">
                      <span
                        className={`p-2 rounded-xl text-xs font-semibold flex items-center space-x-1.5 ${
                          isNarration
                            ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                            : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        }`}
                      >
                        {isNarration ? <BookOpen className="w-3.5 h-3.5" /> : <Users className="w-3.5 h-3.5" />}
                        <span>{isNarration ? 'Sách nói' : 'Hội thoại'}</span>
                      </span>
                      <span className="text-[10px] text-slate-500 font-mono bg-slate-800/80 px-2 py-0.5 rounded-full">
                        v{p.version}
                      </span>
                    </div>

                    <button
                      onClick={e => handleDelete(p, e)}
                      title="Xóa dự án"
                      className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Title & Description */}
                  <div>
                    <h3 className="text-base font-bold text-white group-hover:text-purple-300 transition-colors line-clamp-1">
                      {p.title}
                    </h3>
                    <p className="text-xs text-slate-400 mt-1 line-clamp-2 min-h-[2rem]">
                      {p.description || 'Chưa có phần mô tả.'}
                    </p>
                  </div>
                </div>

                {/* Progress & Stats */}
                <div className="space-y-3 pt-3 border-t border-slate-800/80">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <div className="flex items-center space-x-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      <span>{p.completed_segment_count}/{p.segment_count} phân đoạn</span>
                    </div>
                    <div className="flex items-center space-x-1 font-mono text-purple-300">
                      <Music className="w-3.5 h-3.5" />
                      <span>{p.total_audio_duration_s.toFixed(1)}s</span>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${
                        progress === 100 ? 'bg-emerald-500' : 'bg-purple-500'
                      }`}
                      style={{ width: `${progress}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between pt-1 text-[11px] text-slate-500">
                    <span className="flex items-center space-x-1">
                      <Clock className="w-3 h-3" />
                      <span>{new Date(p.updated_at).toLocaleDateString('vi-VN')}</span>
                    </span>
                    <span className="flex items-center space-x-1 text-purple-400 font-semibold group-hover:translate-x-1 transition-transform">
                      <span>Mở phòng thu</span>
                      <ExternalLink className="w-3 h-3" />
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Project Modal */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-base font-bold text-white flex items-center space-x-2">
                <FolderPlus className="w-5 h-5 text-emerald-400" />
                <span>Tạo Dự Án Audio Studio Mới</span>
              </h2>
              <button
                onClick={() => setIsCreateOpen(false)}
                className="text-slate-500 hover:text-white p-1 rounded-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Tiêu đề dự án <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={newTitle}
                  onChange={e => setNewTitle(e.target.value)}
                  placeholder="Ví dụ: Audio Book Chương 1 - Truyện Kiều"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Mô tả dự án (tùy chọn)
                </label>
                <textarea
                  rows={2}
                  value={newDescription}
                  onChange={e => setNewDescription(e.target.value)}
                  placeholder="Ghi chú về nội dung, phong cách giọng điệu hoặc mục tiêu xuất bản..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Loại hình phòng thu (Project Type)
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setNewType('narration')}
                    className={`p-3 rounded-xl border text-left transition-all flex flex-col space-y-1 ${
                      newType === 'narration'
                        ? 'border-blue-500 bg-blue-500/10 text-white'
                        : 'border-slate-800 bg-slate-800/40 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center space-x-2 font-semibold text-xs">
                      <BookOpen className="w-4 h-4 text-blue-400" />
                      <span>Sách nói (Narration)</span>
                    </div>
                    <p className="text-[11px] text-slate-400 leading-tight">
                      Kịch bản văn bản dài, tự động phân đoạn thông minh, tạo giọng đọc đơn hoặc chương hồi.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setNewType('dialogue')}
                    className={`p-3 rounded-xl border text-left transition-all flex flex-col space-y-1 ${
                      newType === 'dialogue'
                        ? 'border-emerald-500 bg-emerald-500/10 text-white'
                        : 'border-slate-800 bg-slate-800/40 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center space-x-2 font-semibold text-xs">
                      <Users className="w-4 h-4 text-emerald-400" />
                      <span>Hội thoại (Dialogue)</span>
                    </div>
                    <p className="text-[11px] text-slate-400 leading-tight">
                      Kịch bản nhiều nhân vật, gắn giọng và màu đại diện riêng, quản lý lượt thoại và khoảng lặng.
                    </p>
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={creating || !newTitle.trim()}
                  className="px-5 py-2 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 transition-colors"
                >
                  {creating ? 'Đang tạo...' : 'Tạo Dự Án Ngay'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
