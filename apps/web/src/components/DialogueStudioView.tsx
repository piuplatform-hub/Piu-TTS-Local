import React, { useState, useEffect, useRef } from 'react';
import {
  ArrowLeft,
  Play,
  Pause,
  RotateCcw,
  Sparkles,
  Plus,
  Trash2,
  Sliders,
  AlertCircle,
  CheckCircle,
  Clock,
  RefreshCw,
  Save,
  Users,
  UserPlus,
  MessageSquare,
  Edit2,
} from 'lucide-react';
import { api, ApiError } from '../api/client';
import { ProjectDetail, ScriptSegment, Character } from '../types';
import { MasterExportModal } from './MasterExportModal';

interface DialogueStudioViewProps {
  projectId: string;
  onBack: () => void;
}

const PRESET_COLORS = [
  '#10b981', // emerald
  '#3b82f6', // blue
  '#8b5cf6', // purple
  '#f59e0b', // amber
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#f97316', // orange
  '#6366f1', // indigo
];

export const DialogueStudioView: React.FC<DialogueStudioViewProps> = ({ projectId, onBack }) => {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Character Modal state
  const [isCharModalOpen, setIsCharModalOpen] = useState<boolean>(false);
  const [editingChar, setEditingChar] = useState<Character | null>(null);
  const [charName, setCharName] = useState<string>('');
  const [charDesc, setCharDesc] = useState<string>('');
  const [charColor, setCharColor] = useState<string>(PRESET_COLORS[0]);
  const [charEngine, setCharEngine] = useState<string>('vieneu-tts');
  const [charVoice, setCharVoice] = useState<string>('mai_anh');

  // Master Export Modal state
  const [isExportOpen, setIsExportOpen] = useState<boolean>(false);

  // Audio Playback
  const [playingSegmentId, setPlayingSegmentId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Text edits buffer
  const [textEdits, setTextEdits] = useState<Record<string, string>>({});

  const fetchProject = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getProject(projectId);
      setProject(data);
      const edits: Record<string, string> = {};
      data.segments.forEach(s => {
        edits[s.id] = s.text;
      });
      setTextEdits(edits);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.problem.detail || err.message);
      } else {
        setError(err.message || 'Không thể tải chi tiết dự án hội thoại');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProject();
  }, [projectId]);

  // Auto-poll when in-flight jobs exist
  useEffect(() => {
    if (!project) return;
    const hasInFlight = project.segments.some(s => s.status === 'queued' || s.status === 'rendering');
    if (!hasInFlight) return;

    const timer = setInterval(async () => {
      try {
        const data = await api.getProject(projectId);
        setProject(data);
        const stillInFlight = data.segments.some(s => s.status === 'queued' || s.status === 'rendering');
        if (!stillInFlight) {
          clearInterval(timer);
        }
      } catch (e) {
        console.warn('Dialogue auto-poll error', e);
      }
    }, 2000);

    return () => clearInterval(timer);
  }, [project, projectId]);

  // Audio Playback handler
  const handlePlayAudio = async (segmentId: string, artifactId: string) => {
    if (playingSegmentId === segmentId) {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      setPlayingSegmentId(null);
      return;
    }

    if (audioRef.current) {
      audioRef.current.pause();
    }

    try {
      const blobUrl = await api.fetchArtifactAudioBlob(artifactId);
      const audio = new Audio(blobUrl);
      audioRef.current = audio;
      setPlayingSegmentId(segmentId);

      audio.onended = () => {
        setPlayingSegmentId(null);
        window.URL.revokeObjectURL(blobUrl);
      };
      audio.onerror = () => {
        setPlayingSegmentId(null);
        window.URL.revokeObjectURL(blobUrl);
        alert('Không thể phát file âm thanh này.');
      };

      await audio.play();
    } catch (err: any) {
      console.warn('Playback error', err);
      setPlayingSegmentId(null);
    }
  };

  // Reconcile
  const handleReconcile = async () => {
    try {
      setActionLoading('reconcile');
      const updated = await api.reconcileProject(projectId);
      setProject(updated);
    } catch (err: any) {
      alert(`Đồng bộ thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Open Create Character Modal
  const handleOpenAddCharacter = () => {
    setEditingChar(null);
    setCharName('');
    setCharDesc('');
    setCharColor(PRESET_COLORS[Math.floor(Math.random() * PRESET_COLORS.length)]);
    setCharEngine('vieneu-tts');
    setCharVoice('mai_anh');
    setIsCharModalOpen(true);
  };

  // Open Edit Character Modal
  const handleOpenEditCharacter = (char: Character) => {
    setEditingChar(char);
    setCharName(char.name);
    setCharDesc(char.description || '');
    setCharColor(char.avatar_color || PRESET_COLORS[0]);
    setCharEngine(char.engine_id);
    setCharVoice(char.voice_id);
    setIsCharModalOpen(true);
  };

  // Save Character (Create / Update)
  const handleSaveCharacter = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!project || !charName.trim()) return;

    try {
      setActionLoading('save_char');
      if (editingChar) {
        await api.updateCharacter(project.id, editingChar.id, {
          name: charName.trim(),
          description: charDesc.trim() || undefined,
          avatar_color: charColor,
          engine_id: charEngine,
          voice_id: charVoice,
          expected_project_version: project.version,
        });
      } else {
        await api.createCharacter(project.id, {
          name: charName.trim(),
          description: charDesc.trim() || undefined,
          avatar_color: charColor,
          engine_id: charEngine,
          voice_id: charVoice,
          expected_project_version: project.version,
        });
      }
      setIsCharModalOpen(false);
      await fetchProject();
    } catch (err: any) {
      alert(`Lưu nhân vật thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Delete Character
  const handleDeleteCharacter = async (char: Character) => {
    if (!project) return;
    if (!window.confirm(`Bạn có chắc chắn muốn xóa nhân vật "${char.name}"?`)) return;

    try {
      setActionLoading(`del_char_${char.id}`);
      await api.deleteCharacter(project.id, char.id, project.version);
      await fetchProject();
    } catch (err: any) {
      alert(`Xóa nhân vật thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Add Dialogue Line (Segment)
  const handleAddDialogueLine = async (charId?: string) => {
    if (!project) return;
    try {
      setActionLoading('add_line');
      const targetChar = project.characters.find(c => c.id === charId) || project.characters[0];
      const nextOrder = project.segments.length;

      await api.addSegment(project.id, {
        sequence_order: nextOrder,
        character_id: targetChar?.id,
        text: 'Lời thoại mới của nhân vật...',
        language: targetChar?.engine_id === 'qwen3-tts' ? 'zh' : 'vi',
        engine_id: targetChar?.engine_id || 'vieneu-tts',
        voice_id: targetChar?.voice_id || 'mai_anh',
        pause_after_ms: 400, // natural turn-taking pause
        expected_project_version: project.version,
      });
      await fetchProject();
    } catch (err: any) {
      alert(`Thêm câu thoại thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Assign Character to Segment
  const handleAssignCharacter = async (seg: ScriptSegment, charId: string) => {
    if (!project) return;
    const char = project.characters.find(c => c.id === charId);
    if (!char) return;

    try {
      setActionLoading(`assign_${seg.id}`);
      await api.updateSegment(project.id, seg.id, {
        character_id: char.id,
        engine_id: char.engine_id,
        voice_id: char.voice_id,
        language: char.engine_id === 'qwen3-tts' ? 'zh' : 'vi',
        expected_segment_version: seg.version,
        expected_project_version: project.version,
      });
      await fetchProject();
    } catch (err: any) {
      alert(`Gán nhân vật thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Save Segment Text
  const handleSaveSegmentText = async (seg: ScriptSegment) => {
    if (!project) return;
    const currentText = textEdits[seg.id];
    if (currentText === undefined || currentText === seg.text) return;

    try {
      setActionLoading(`save_${seg.id}`);
      await api.updateSegment(project.id, seg.id, {
        text: currentText,
        expected_segment_version: seg.version,
        expected_project_version: project.version,
      });
      await fetchProject();
    } catch (err: any) {
      alert(`Cập nhật lời thoại thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Update Pause
  const handleUpdatePause = async (seg: ScriptSegment, pauseMs: number) => {
    if (!project) return;
    try {
      setActionLoading(`pause_${seg.id}`);
      await api.updateSegment(project.id, seg.id, {
        pause_after_ms: pauseMs,
        expected_segment_version: seg.version,
        expected_project_version: project.version,
      });
      await fetchProject();
    } catch (err: any) {
      alert(`Cập nhật thời gian nghỉ thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Render Single Line
  const handleRenderLine = async (seg: ScriptSegment) => {
    if (!project) return;
    if (textEdits[seg.id] && textEdits[seg.id] !== seg.text) {
      await handleSaveSegmentText(seg);
    }

    try {
      setActionLoading(`render_${seg.id}`);
      await api.renderSegment(project.id, seg.id);
      await fetchProject();
    } catch (err: any) {
      alert(`Khởi tạo âm thanh thoại thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Batch Render
  const handleBatchRender = async () => {
    if (!project) return;
    try {
      setActionLoading('batch_render');
      await api.renderBatch(project.id, { only_stale_or_draft: true });
      await fetchProject();
    } catch (err: any) {
      alert(`Tạo hàng loạt thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Delete Segment
  const handleDeleteSegment = async (seg: ScriptSegment) => {
    if (!project) return;
    if (!window.confirm('Bạn có chắc chắn muốn xóa câu thoại này?')) return;

    try {
      setActionLoading(`del_${seg.id}`);
      await api.deleteSegment(project.id, seg.id, project.version);
      await fetchProject();
    } catch (err: any) {
      alert(`Xóa câu thoại thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading && !project) {
    return (
      <div className="py-24 flex flex-col items-center justify-center space-y-3">
        <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-slate-400">Đang tải phòng thu kịch truyền thanh...</p>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="max-w-4xl mx-auto py-12 px-4 text-center space-y-4">
        <AlertCircle className="w-12 h-12 text-red-400 mx-auto" />
        <h2 className="text-lg font-bold text-white">Không thể tải dự án hội thoại</h2>
        <p className="text-xs text-slate-400">{error || 'Dự án không tồn tại'}</p>
        <button
          onClick={onBack}
          className="inline-flex items-center space-x-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Quay lại danh sách dự án</span>
        </button>
      </div>
    );
  }

  const completedCount = project.segments.filter(s => s.status === 'completed').length;
  const staleCount = project.segments.filter(s => s.status === 'stale').length;
  const draftCount = project.segments.filter(s => s.status === 'draft').length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Top Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center space-x-4">
          <button
            onClick={onBack}
            className="p-2 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Quay lại danh sách"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center space-x-3">
              <h1 className="text-xl font-bold text-white tracking-tight">{project.title}</h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Hội Thoại Nhiều Nhân Vật • v{project.version}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              {project.description || 'Kịch bản kịch truyền thanh, đối thoại podcast kết hợp đa engine VieNeu & Qwen3'}
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Add Character */}
          <button
            onClick={handleOpenAddCharacter}
            className="flex items-center space-x-1.5 px-3 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-700/80 rounded-xl text-xs font-medium text-slate-200 transition-colors"
          >
            <UserPlus className="w-3.5 h-3.5 text-emerald-400" />
            <span>Thêm Nhân Vật</span>
          </button>

          {/* Add Line */}
          <button
            onClick={() => handleAddDialogueLine()}
            disabled={actionLoading === 'add_line'}
            className="flex items-center space-x-1.5 px-3 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-700/80 rounded-xl text-xs font-medium text-slate-200 transition-colors"
          >
            <Plus className="w-3.5 h-3.5 text-emerald-400" />
            <span>Thêm Câu Thoại</span>
          </button>

          {/* Batch render */}
          {(staleCount > 0 || draftCount > 0) && (
            <button
              onClick={handleBatchRender}
              disabled={actionLoading === 'batch_render'}
              className="flex items-center space-x-1.5 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold shadow-md transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Tạo Lại Cần Cập Nhật ({staleCount + draftCount})</span>
            </button>
          )}

          {/* Reconcile */}
          <button
            onClick={handleReconcile}
            disabled={actionLoading === 'reconcile'}
            title="Đồng bộ trạng thái xử lý nền"
            className="p-2 bg-slate-900 border border-slate-800 rounded-xl text-slate-400 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${actionLoading === 'reconcile' ? 'animate-spin' : ''}`} />
          </button>

          {/* Master Export */}
          <button
            onClick={() => setIsExportOpen(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-emerald-600 hover:from-purple-500 hover:to-emerald-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-emerald-950/40 transition-all ml-auto sm:ml-0"
          >
            <Sliders className="w-4 h-4" />
            <span>Xuất Bản Master DSP</span>
          </button>
        </div>
      </div>

      {/* Character Personas Roster Panel */}
      <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Users className="w-4 h-4 text-emerald-400" />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Danh Sách Nhân Vật Trong Vở Kịch ({project.characters.length})
            </h3>
          </div>
          <button
            onClick={handleOpenAddCharacter}
            className="text-xs text-emerald-400 hover:text-emerald-300 font-semibold flex items-center space-x-1"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Tạo nhân vật mới</span>
          </button>
        </div>

        {project.characters.length === 0 ? (
          <div className="p-4 rounded-xl border border-dashed border-slate-800 text-center text-xs text-slate-500">
            Chưa có nhân vật nào được tạo. Hãy tạo ít nhất 2 nhân vật để bắt đầu phân vai đối thoại.
          </div>
        ) : (
          <div className="flex flex-wrap gap-3">
            {project.characters.map(char => (
              <div
                key={char.id}
                className="group p-2.5 rounded-xl bg-slate-950 border border-slate-800 hover:border-slate-700 flex items-center space-x-3 transition-colors"
              >
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold shadow"
                  style={{ backgroundColor: char.avatar_color }}
                >
                  {char.name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-bold text-white">{char.name}</span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {char.engine_id === 'vieneu-tts' ? 'VieNeu 48kHz' : 'Qwen3 24kHz'}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Giọng: <span className="text-slate-200 font-medium">{char.voice_id}</span>
                  </p>
                </div>
                <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity pl-2">
                  <button
                    onClick={() => handleOpenEditCharacter(char)}
                    className="p-1 text-slate-400 hover:text-white rounded"
                  >
                    <Edit2 className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => handleDeleteCharacter(char)}
                    className="p-1 text-slate-400 hover:text-red-400 rounded"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Progress metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
          <span className="text-slate-500 block text-[11px]">TỔNG CÂU THOẠI</span>
          <span className="text-white font-bold text-base mt-0.5 block">{project.segments.length} câu</span>
        </div>
        <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
          <span className="text-slate-500 block text-[11px]">ĐÃ THU ÂM XONG</span>
          <span className="text-emerald-400 font-bold text-base mt-0.5 block">
            {completedCount} / {project.segments.length}
          </span>
        </div>
        <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
          <span className="text-slate-500 block text-[11px]">CẦN CẬP NHẬT (STALE)</span>
          <span className={`font-bold text-base mt-0.5 block ${staleCount > 0 ? 'text-amber-400' : 'text-slate-400'}`}>
            {staleCount} câu
          </span>
        </div>
        <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
          <span className="text-slate-500 block text-[11px]">MASTER EXPORTS</span>
          <span className="text-purple-300 font-bold text-base mt-0.5 block">
            {project.exports?.length || 0} bản
          </span>
        </div>
      </div>

      {/* Dialogue Timeline Stream */}
      <div className="space-y-4">
        {project.segments.length === 0 ? (
          <div className="p-12 text-center border border-dashed border-slate-800 rounded-2xl bg-slate-900/40 space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center mx-auto">
              <MessageSquare className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Chưa có câu thoại nào trong kịch bản</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
                Tạo các nhân vật sau đó bấm &quot;Thêm Câu Thoại&quot; để biên tập lượt nói và căn thời gian chuyển cảnh.
              </p>
            </div>
            <button
              onClick={() => handleAddDialogueLine()}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition-colors"
            >
              Thêm Câu Thoại Đầu Tiên
            </button>
          </div>
        ) : (
          project.segments.map((seg, idx) => {
            const isPlaying = playingSegmentId === seg.id;
            const currentEditText = textEdits[seg.id] ?? seg.text;
            const hasUnsavedText = currentEditText !== seg.text;
            const assignedChar = project.characters.find(c => c.id === seg.character_id);

            return (
              <div
                key={seg.id}
                className={`p-4 rounded-2xl border transition-all space-y-3 ${
                  seg.status === 'completed'
                    ? 'bg-slate-900/80 border-slate-800 hover:border-slate-700'
                    : seg.status === 'stale'
                    ? 'bg-amber-950/10 border-amber-500/30'
                    : seg.status === 'rendering' || seg.status === 'queued'
                    ? 'bg-emerald-950/10 border-emerald-500/30'
                    : 'bg-slate-900/40 border-slate-800'
                }`}
              >
                {/* Dialogue Header */}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center space-x-3">
                    <span className="w-6 h-6 rounded-lg bg-slate-800 flex items-center justify-center text-xs font-mono font-bold text-slate-300">
                      #{idx + 1}
                    </span>

                    {/* Character Avatar & Selector */}
                    <div className="flex items-center space-x-2">
                      <div
                        className="w-6 h-6 rounded-full flex items-center justify-center text-white text-[11px] font-bold shadow"
                        style={{ backgroundColor: assignedChar?.avatar_color || '#64748b' }}
                      >
                        {assignedChar?.name?.charAt(0).toUpperCase() || '?'}
                      </div>
                      <select
                        value={seg.character_id || ''}
                        onChange={e => handleAssignCharacter(seg, e.target.value)}
                        className="bg-slate-800 border border-slate-700 text-xs font-bold text-white rounded-lg px-2.5 py-1 focus:outline-none focus:border-emerald-500"
                      >
                        <option value="" disabled>-- Chọn Nhân Vật --</option>
                        {project.characters.map(c => (
                          <option key={c.id} value={c.id}>
                            {c.name} ({c.engine_id === 'vieneu-tts' ? 'VieNeu' : 'Qwen3'})
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Status Badge */}
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider flex items-center space-x-1 ${
                        seg.status === 'completed'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : seg.status === 'stale'
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : seg.status === 'rendering'
                          ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20 animate-pulse'
                          : seg.status === 'queued'
                          ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {seg.status === 'completed' && <CheckCircle className="w-3 h-3" />}
                      {seg.status === 'stale' && <AlertCircle className="w-3 h-3" />}
                      {seg.status === 'rendering' && <RotateCcw className="w-3 h-3 animate-spin" />}
                      <span>
                        {seg.status === 'completed'
                          ? 'Hoàn thành'
                          : seg.status === 'stale'
                          ? 'Cần tạo lại'
                          : seg.status === 'rendering'
                          ? 'Đang render'
                          : seg.status === 'queued'
                          ? 'Đang chờ'
                          : 'Bản nháp'}
                      </span>
                    </span>
                  </div>

                  {/* Turn-taking Pause Control & Actions */}
                  <div className="flex items-center space-x-3 text-xs">
                    <div className="flex items-center space-x-1 text-slate-400">
                      <Clock className="w-3 h-3" />
                      <span className="text-[11px]">Nghỉ chuyển lượt:</span>
                      <select
                        value={seg.pause_after_ms}
                        onChange={e => handleUpdatePause(seg, parseInt(e.target.value, 10))}
                        className="bg-slate-800 border border-slate-700 text-slate-300 rounded px-2 py-1 text-xs focus:outline-none"
                      >
                        <option value={200}>0.2s</option>
                        <option value={400}>0.4s (Chuẩn)</option>
                        <option value={600}>0.6s</option>
                        <option value={1000}>1.0s (Chuyển cảnh)</option>
                        <option value={1500}>1.5s</option>
                      </select>
                    </div>

                    <button
                      onClick={() => handleDeleteSegment(seg)}
                      title="Xóa câu thoại"
                      className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Dialogue Textarea */}
                <div className="relative">
                  <textarea
                    rows={2}
                    value={currentEditText}
                    onChange={e => setTextEdits(prev => ({ ...prev, [seg.id]: e.target.value }))}
                    className={`w-full bg-slate-950/70 border rounded-xl p-3 text-sm text-slate-100 focus:outline-none transition-colors ${
                      hasUnsavedText
                        ? 'border-amber-500/80 focus:border-amber-400'
                        : 'border-slate-800 focus:border-emerald-500'
                    }`}
                  />

                  {hasUnsavedText && (
                    <div className="absolute right-3 bottom-3 flex items-center space-x-2">
                      <span className="text-[10px] text-amber-400 font-semibold bg-amber-950/80 px-2 py-0.5 rounded-md border border-amber-500/30">
                        Chưa lưu
                      </span>
                      <button
                        onClick={() => handleSaveSegmentText(seg)}
                        disabled={actionLoading === `save_${seg.id}`}
                        className="flex items-center space-x-1 px-2.5 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded-md text-xs font-semibold shadow transition-colors"
                      >
                        <Save className="w-3 h-3" />
                        <span>Lưu</span>
                      </button>
                    </div>
                  )}
                </div>

                {/* Controls & Playback */}
                <div className="flex items-center justify-between pt-1 text-xs">
                  <div className="flex items-center space-x-2">
                    {seg.active_artifact_id && (
                      <button
                        onClick={() => handlePlayAudio(seg.id, seg.active_artifact_id!)}
                        className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-semibold transition-colors ${
                          isPlaying
                            ? 'bg-emerald-500 text-slate-950 shadow-md'
                            : 'bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30 border border-emerald-500/30'
                        }`}
                      >
                        {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                        <span>{isPlaying ? 'Tạm dừng' : 'Nghe thoại'}</span>
                      </button>
                    )}
                  </div>

                  <button
                    onClick={() => handleRenderLine(seg)}
                    disabled={actionLoading === `render_${seg.id}` || seg.status === 'rendering'}
                    className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-semibold text-xs transition-all ${
                      seg.status === 'completed'
                        ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                        : seg.status === 'stale'
                        ? 'bg-amber-600 hover:bg-amber-500 text-white shadow-md'
                        : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-md'
                    }`}
                  >
                    {actionLoading === `render_${seg.id}` ? (
                      <RotateCcw className="w-3 h-3 animate-spin" />
                    ) : (
                      <Sparkles className="w-3 h-3" />
                    )}
                    <span>
                      {seg.status === 'completed'
                        ? 'Thu âm lại'
                        : seg.status === 'stale'
                        ? 'Thu âm lại lời đã sửa'
                        : 'Thu âm câu này'}
                    </span>
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Character Modal (Create / Edit) */}
      {isCharModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md shadow-2xl p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-base font-bold text-white flex items-center space-x-2">
                <Users className="w-5 h-5 text-emerald-400" />
                <span>{editingChar ? 'Chỉnh Sửa Nhân Vật' : 'Tạo Nhân Vật Mới'}</span>
              </h2>
              <button
                onClick={() => setIsCharModalOpen(false)}
                className="text-slate-500 hover:text-white"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveCharacter} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Tên nhân vật <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={charName}
                  onChange={e => setCharName(e.target.value)}
                  placeholder="Ví dụ: Người Dẫn Chuyện, Kiều, Kim Trọng..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Mô tả đặc điểm / tính cách
                </label>
                <input
                  type="text"
                  value={charDesc}
                  onChange={e => setCharDesc(e.target.value)}
                  placeholder="Ví dụ: Giọng trầm ấm, điềm đạm"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Màu sắc nhận diện (Avatar Badge)
                </label>
                <div className="flex items-center space-x-2">
                  {PRESET_COLORS.map(c => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => setCharColor(c)}
                      className={`w-7 h-7 rounded-full transition-transform ${
                        charColor === c ? 'scale-125 ring-2 ring-white' : 'opacity-70 hover:opacity-100'
                      }`}
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Công nghệ Engine
                  </label>
                  <select
                    value={charEngine}
                    onChange={e => {
                      const val = e.target.value;
                      setCharEngine(val);
                      if (val === 'qwen3-tts') setCharVoice('vivian');
                      else setCharVoice('mai_anh');
                    }}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none"
                  >
                    <option value="vieneu-tts">VieNeu-TTS (48kHz CPU)</option>
                    <option value="qwen3-tts">Qwen3-TTS (24kHz GPU)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Giọng đọc phân công
                  </label>
                  <select
                    value={charVoice}
                    onChange={e => setCharVoice(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none"
                  >
                    {charEngine === 'vieneu-tts' ? (
                      <>
                        <option value="mai_anh">Mai Anh (Nữ chuẩn)</option>
                        <option value="nam_trung">Nam Trung (Nam chuẩn)</option>
                      </>
                    ) : (
                      <>
                        <option value="vivian">Vivian (Trung/Anh)</option>
                      </>
                    )}
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsCharModalOpen(false)}
                  className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={actionLoading === 'save_char' || !charName.trim()}
                  className="px-5 py-2 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 transition-colors"
                >
                  {actionLoading === 'save_char' ? 'Đang lưu...' : 'Lưu Nhân Vật'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Master Export Modal */}
      {isExportOpen && (
        <MasterExportModal
          project={project}
          isOpen={isExportOpen}
          onClose={() => setIsExportOpen(false)}
          onExportSuccess={async () => {
            await fetchProject();
          }}
        />
      )}
    </div>
  );
};
