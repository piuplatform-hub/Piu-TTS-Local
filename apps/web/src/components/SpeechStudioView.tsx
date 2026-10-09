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
  History,
  AlertCircle,
  CheckCircle,
  Clock,
  RefreshCw,
  Scissors,
  Save,
  Volume2,
  FileText,
} from 'lucide-react';
import { api, ApiError } from '../api/client';
import { ProjectDetail, ScriptSegment, SegmentRevision, TextSegmentationResult } from '../types';
import { MasterExportModal } from './MasterExportModal';

interface SpeechStudioViewProps {
  projectId: string;
  onBack: () => void;
}

export const SpeechStudioView: React.FC<SpeechStudioViewProps> = ({ projectId, onBack }) => {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Auto-segment Modal state
  const [isAutoSegmentOpen, setIsAutoSegmentOpen] = useState<boolean>(false);
  const [rawText, setRawText] = useState<string>('');
  const [segmentLang, setSegmentLang] = useState<'vi' | 'zh' | 'en'>('vi');
  const [maxChars, setMaxChars] = useState<number>(220);
  const [previewResult, setPreviewResult] = useState<TextSegmentationResult | null>(null);
  const [previewing, setPreviewing] = useState<boolean>(false);

  // Master Export Modal state
  const [isExportOpen, setIsExportOpen] = useState<boolean>(false);

  // Revision History Drawer state
  const [activeRevisionSegment, setActiveRevisionSegment] = useState<ScriptSegment | null>(null);

  // Mini Audio Player State
  const [playingSegmentId, setPlayingSegmentId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Text edits tracking per segment: { [segId]: editedText }
  const [textEdits, setTextEdits] = useState<Record<string, string>>({});

  const fetchProject = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getProject(projectId);
      setProject(data);
      // Initialize text edits buffer
      const edits: Record<string, string> = {};
      data.segments.forEach(s => {
        edits[s.id] = s.text;
      });
      setTextEdits(edits);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.problem.detail || err.message);
      } else {
        setError(err.message || 'Không thể tải chi tiết dự án');
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
        console.warn('Auto-poll error', e);
      }
    }, 2000);

    return () => clearInterval(timer);
  }, [project, projectId]);

  // Audio Playback
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

  // Reconcile status
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

  // Add Segment
  const handleAddSegment = async () => {
    if (!project) return;
    try {
      setActionLoading('add_segment');
      const nextOrder = project.segments.length;
      await api.addSegment(project.id, {
        sequence_order: nextOrder,
        text: 'Nội dung phân đoạn mới...',
        language: 'vi',
        engine_id: 'vieneu-tts',
        voice_id: 'mai_anh',
        pause_after_ms: 300,
        expected_project_version: project.version,
      });
      await fetchProject();
    } catch (err: any) {
      alert(`Thêm phân đoạn thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Save Segment Text Changes (marks stale if text changed)
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
      alert(`Cập nhật văn bản thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Update Pause Duration
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

  // Update Voice & Engine
  const handleUpdateVoice = async (seg: ScriptSegment, engineId: string, voiceId: string) => {
    if (!project) return;
    try {
      setActionLoading(`voice_${seg.id}`);
      await api.updateSegment(project.id, seg.id, {
        engine_id: engineId,
        voice_id: voiceId,
        expected_segment_version: seg.version,
        expected_project_version: project.version,
      });
      await fetchProject();
    } catch (err: any) {
      alert(`Đổi giọng thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Delete Segment
  const handleDeleteSegment = async (seg: ScriptSegment) => {
    if (!project) return;
    if (!window.confirm(`Bạn có chắc muốn xóa phân đoạn #${seg.sequence_order + 1}?`)) return;

    try {
      setActionLoading(`del_${seg.id}`);
      await api.deleteSegment(project.id, seg.id, project.version);
      await fetchProject();
    } catch (err: any) {
      alert(`Xóa phân đoạn thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Render Single Segment
  const handleRenderSegment = async (seg: ScriptSegment) => {
    if (!project) return;
    // Auto-save any pending text edit first
    if (textEdits[seg.id] && textEdits[seg.id] !== seg.text) {
      await handleSaveSegmentText(seg);
    }

    try {
      setActionLoading(`render_${seg.id}`);
      await api.renderSegment(project.id, seg.id);
      await fetchProject();
    } catch (err: any) {
      alert(`Khởi tạo tạo âm thanh thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  // Batch Render (All stale or draft)
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

  // Auto Segment Preview
  const handlePreviewSegmentation = async () => {
    if (!rawText.trim()) return;
    try {
      setPreviewing(true);
      const res = await api.previewTextSegmentation({
        text: rawText.trim(),
        language: segmentLang,
        max_chars_per_segment: maxChars,
      });
      setPreviewResult(res);
    } catch (err: any) {
      alert(`Xem trước phân đoạn thất bại: ${err.message}`);
    } finally {
      setPreviewing(false);
    }
  };

  // Apply Auto-segmentation to Project
  const handleApplyAutoSegmentation = async () => {
    if (!project || !rawText.trim()) return;
    try {
      setActionLoading('apply_segmentation');
      await api.autoSegmentProject(project.id, {
        text: rawText.trim(),
        language: segmentLang,
        max_chars_per_segment: maxChars,
        default_engine_id: segmentLang === 'zh' ? 'qwen3-tts' : 'vieneu-tts',
        default_voice_id: segmentLang === 'zh' ? 'vivian' : 'mai_anh',
        expected_project_version: project.version,
      });
      setIsAutoSegmentOpen(false);
      setRawText('');
      setPreviewResult(null);
      await fetchProject();
    } catch (err: any) {
      alert(`Áp dụng phân đoạn thất bại: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading && !project) {
    return (
      <div className="py-24 flex flex-col items-center justify-center space-y-3">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-slate-400">Đang tải phòng thu sách nói...</p>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="max-w-4xl mx-auto py-12 px-4 text-center space-y-4">
        <AlertCircle className="w-12 h-12 text-red-400 mx-auto" />
        <h2 className="text-lg font-bold text-white">Không thể tải dự án</h2>
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
      {/* Top Navigation Bar */}
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
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                Sách Nói • v{project.version}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              {project.description || 'Phòng thu narration đọc sách và tài liệu dài'}
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Auto segment */}
          <button
            onClick={() => setIsAutoSegmentOpen(true)}
            className="flex items-center space-x-1.5 px-3 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-700/80 rounded-xl text-xs font-medium text-slate-200 transition-colors"
          >
            <Scissors className="w-3.5 h-3.5 text-blue-400" />
            <span>Phân Đoạn Văn Bản</span>
          </button>

          {/* Add segment */}
          <button
            onClick={handleAddSegment}
            disabled={actionLoading === 'add_segment'}
            className="flex items-center space-x-1.5 px-3 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-700/80 rounded-xl text-xs font-medium text-slate-200 transition-colors"
          >
            <Plus className="w-3.5 h-3.5 text-emerald-400" />
            <span>Thêm Phân Đoạn</span>
          </button>

          {/* Batch render */}
          {(staleCount > 0 || draftCount > 0) && (
            <button
              onClick={handleBatchRender}
              disabled={actionLoading === 'batch_render'}
              className="flex items-center space-x-1.5 px-3.5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow-md transition-colors"
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
            className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-purple-950/40 transition-all ml-auto sm:ml-0"
          >
            <Sliders className="w-4 h-4" />
            <span>Xuất Bản Master DSP</span>
          </button>
        </div>
      </div>

      {/* Progress & Stat Banner */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
          <span className="text-slate-500 block text-[11px]">TỔNG PHÂN ĐOẠN</span>
          <span className="text-white font-bold text-base mt-0.5 block">{project.segments.length} đoạn</span>
        </div>
        <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
          <span className="text-slate-500 block text-[11px]">ĐÃ TẠO XONG</span>
          <span className="text-emerald-400 font-bold text-base mt-0.5 block">
            {completedCount} / {project.segments.length}
          </span>
        </div>
        <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
          <span className="text-slate-500 block text-[11px]">CẦN TẠO LẠI (STALE)</span>
          <span className={`font-bold text-base mt-0.5 block ${staleCount > 0 ? 'text-amber-400' : 'text-slate-400'}`}>
            {staleCount} đoạn
          </span>
        </div>
        <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
          <span className="text-slate-500 block text-[11px]">BẢN MASTER EXPORT</span>
          <span className="text-purple-300 font-bold text-base mt-0.5 block">
            {project.exports?.length || 0} bản
          </span>
        </div>
      </div>

      {/* Segments Stream */}
      <div className="space-y-4">
        {project.segments.length === 0 ? (
          <div className="p-12 text-center border border-dashed border-slate-800 rounded-2xl bg-slate-900/40 space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-blue-500/10 text-blue-400 flex items-center justify-center mx-auto">
              <FileText className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">Chưa có phân đoạn nào trong sách nói</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
                Dán toàn bộ văn bản của chương để hệ thống tự động tách câu chuẩn ngôn ngữ, hoặc thêm từng đoạn thủ công.
              </p>
            </div>
            <div className="flex justify-center gap-3">
              <button
                onClick={() => setIsAutoSegmentOpen(true)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition-colors"
              >
                Dán và Tự Động Phân Đoạn
              </button>
              <button
                onClick={handleAddSegment}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition-colors"
              >
                Thêm Đoạn Thủ Công
              </button>
            </div>
          </div>
        ) : (
          project.segments.map((seg, idx) => {
            const isPlaying = playingSegmentId === seg.id;
            const currentEditText = textEdits[seg.id] ?? seg.text;
            const hasUnsavedText = currentEditText !== seg.text;

            return (
              <div
                key={seg.id}
                className={`p-4 rounded-2xl border transition-all space-y-3 ${
                  seg.status === 'completed'
                    ? 'bg-slate-900/80 border-slate-800 hover:border-slate-700'
                    : seg.status === 'stale'
                    ? 'bg-amber-950/10 border-amber-500/30'
                    : seg.status === 'rendering' || seg.status === 'queued'
                    ? 'bg-blue-950/10 border-blue-500/30'
                    : 'bg-slate-900/40 border-slate-800'
                }`}
              >
                {/* Segment Header */}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center space-x-2">
                    <span className="w-6 h-6 rounded-lg bg-slate-800 flex items-center justify-center text-xs font-mono font-bold text-slate-300">
                      #{idx + 1}
                    </span>

                    {/* Status Badge */}
                    <span
                      className={`text-[10px] font-semibold px-2.5 py-0.5 rounded-full uppercase tracking-wider flex items-center space-x-1 ${
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
                          ? 'Đang chờ hàng đợi'
                          : 'Bản nháp'}
                      </span>
                    </span>

                    {/* Character length count */}
                    <span className="text-[10px] text-slate-500 font-mono">
                      {currentEditText.length} ký tự
                    </span>
                  </div>

                  {/* Engine & Voice Selectors */}
                  <div className="flex items-center space-x-2 text-xs">
                    <select
                      value={`${seg.engine_id}:${seg.voice_id}`}
                      onChange={e => {
                        const [eng, v] = e.target.value.split(':');
                        handleUpdateVoice(seg, eng, v);
                      }}
                      className="bg-slate-800 border border-slate-700 text-slate-300 rounded-lg px-2.5 py-1 text-xs focus:outline-none focus:border-blue-500"
                    >
                      <option value="vieneu-tts:mai_anh">VieNeu • Mai Anh (Nữ chuẩn)</option>
                      <option value="vieneu-tts:nam_trung">VieNeu • Nam Trung (Nam)</option>
                      <option value="qwen3-tts:vivian">Qwen3 • Vivian (Trung/Anh GPU)</option>
                    </select>

                    {/* Pause selector */}
                    <div className="flex items-center space-x-1 text-slate-400 text-xs">
                      <Clock className="w-3 h-3" />
                      <select
                        value={seg.pause_after_ms}
                        onChange={e => handleUpdatePause(seg, parseInt(e.target.value, 10))}
                        className="bg-slate-800 border border-slate-700 text-slate-300 rounded-lg px-2 py-1 text-xs focus:outline-none"
                      >
                        <option value={0}>Nghỉ 0s</option>
                        <option value={200}>Nghỉ 0.2s</option>
                        <option value={300}>Nghỉ 0.3s</option>
                        <option value={500}>Nghỉ 0.5s</option>
                        <option value={800}>Nghỉ 0.8s</option>
                        <option value={1000}>Nghỉ 1.0s</option>
                        <option value={1500}>Nghỉ 1.5s</option>
                      </select>
                    </div>

                    {/* Delete Segment */}
                    <button
                      onClick={() => handleDeleteSegment(seg)}
                      title="Xóa phân đoạn"
                      className="p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Textarea */}
                <div className="relative">
                  <textarea
                    rows={2}
                    value={currentEditText}
                    onChange={e => setTextEdits(prev => ({ ...prev, [seg.id]: e.target.value }))}
                    className={`w-full bg-slate-950/70 border rounded-xl p-3 text-sm text-slate-100 focus:outline-none transition-colors ${
                      hasUnsavedText
                        ? 'border-amber-500/80 focus:border-amber-400'
                        : 'border-slate-800 focus:border-blue-500'
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

                {/* Segment Controls & Audio Player */}
                <div className="flex items-center justify-between pt-1 text-xs">
                  <div className="flex items-center space-x-2">
                    {/* Audio Playback button if active artifact exists */}
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
                        <span>{isPlaying ? 'Tạm dừng' : 'Nghe thử'}</span>
                      </button>
                    )}

                    {/* Revision history button */}
                    {seg.revisions && seg.revisions.length > 0 && (
                      <button
                        onClick={() => setActiveRevisionSegment(seg)}
                        className="flex items-center space-x-1 text-slate-400 hover:text-slate-200 px-2.5 py-1.5 rounded-lg bg-slate-800/40 hover:bg-slate-800 border border-slate-700/40 transition-colors text-[11px]"
                      >
                        <History className="w-3 h-3 text-purple-400" />
                        <span>Lịch sử ({seg.revisions.length} bản)</span>
                      </button>
                    )}
                  </div>

                  {/* Render Button */}
                  <button
                    onClick={() => handleRenderSegment(seg)}
                    disabled={actionLoading === `render_${seg.id}` || seg.status === 'rendering'}
                    className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-semibold text-xs transition-all ${
                      seg.status === 'completed'
                        ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                        : seg.status === 'stale'
                        ? 'bg-amber-600 hover:bg-amber-500 text-white shadow-md'
                        : 'bg-blue-600 hover:bg-blue-500 text-white shadow-md'
                    }`}
                  >
                    {actionLoading === `render_${seg.id}` ? (
                      <RotateCcw className="w-3 h-3 animate-spin" />
                    ) : (
                      <Sparkles className="w-3 h-3" />
                    )}
                    <span>
                      {seg.status === 'completed'
                        ? 'Tạo lại'
                        : seg.status === 'stale'
                        ? 'Tạo lại đoạn đã sửa'
                        : 'Tạo âm thanh'}
                    </span>
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Auto Segmentation Modal */}
      {isAutoSegmentOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <Scissors className="w-5 h-5 text-blue-400" />
                <h2 className="text-base font-bold text-white">Tự Động Phân Đoạn Văn Bản Dài</h2>
              </div>
              <button
                onClick={() => setIsAutoSegmentOpen(false)}
                className="text-slate-500 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Ngôn ngữ xử lý
                  </label>
                  <select
                    value={segmentLang}
                    onChange={e => setSegmentLang(e.target.value as any)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none"
                  >
                    <option value="vi">Tiếng Việt (VieNeu-TTS tối ưu)</option>
                    <option value="zh">Tiếng Trung (Mandarin Qwen3 tối ưu)</option>
                    <option value="en">Tiếng Anh</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Giới hạn ký tự tối đa mỗi câu
                  </label>
                  <input
                    type="number"
                    min={40}
                    max={400}
                    value={maxChars}
                    onChange={e => setMaxChars(parseInt(e.target.value, 10))}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Dán nội dung chương hoặc tài liệu cần chuyển đổi
                </label>
                <textarea
                  rows={8}
                  value={rawText}
                  onChange={e => setRawText(e.target.value)}
                  placeholder="Dán toàn bộ văn bản vào đây. Hệ thống sẽ tự động phân tách theo ranh giới ngữ nghĩa và dấu kết thúc câu..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>

              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={handlePreviewSegmentation}
                  disabled={previewing || !rawText.trim()}
                  className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold disabled:opacity-50"
                >
                  {previewing ? 'Đang phân tích...' : 'Xem trước kết quả phân đoạn'}
                </button>

                {previewResult && (
                  <span className="text-xs text-blue-400 font-semibold">
                    Đã phân tích: {previewResult.segment_count} phân đoạn ({previewResult.total_chars} ký tự)
                  </span>
                )}
              </div>

              {/* Preview List */}
              {previewResult && (
                <div className="max-h-48 overflow-y-auto space-y-2 p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-xs">
                  {previewResult.segments.map(s => (
                    <div key={s.index} className="p-2 rounded bg-slate-900 border border-slate-800 flex items-start space-x-2">
                      <span className="text-slate-500 font-mono text-[10px]">#{s.index + 1}</span>
                      <p className="text-slate-300 flex-1">{s.text}</p>
                      <span className="text-slate-500 text-[10px] font-mono">{s.char_count}c</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsAutoSegmentOpen(false)}
                  className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white"
                >
                  Hủy
                </button>
                <button
                  type="button"
                  onClick={handleApplyAutoSegmentation}
                  disabled={actionLoading === 'apply_segmentation' || !rawText.trim()}
                  className="px-5 py-2 rounded-lg text-xs font-bold bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 transition-colors shadow-md"
                >
                  {actionLoading === 'apply_segmentation' ? 'Đang áp dụng...' : 'Áp Dụng Vào Sách Nói'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Revision History Drawer Modal */}
      {activeRevisionSegment && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center space-x-2">
                <History className="w-5 h-5 text-purple-400" />
                <h3 className="text-base font-bold text-white">
                  Lịch Sử Bản Thu Phân Đoạn #{activeRevisionSegment.sequence_order + 1}
                </h3>
              </div>
              <button
                onClick={() => setActiveRevisionSegment(null)}
                className="text-slate-500 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
              {activeRevisionSegment.revisions.map((rev: SegmentRevision) => (
                <div
                  key={rev.id}
                  className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="font-semibold text-purple-300">
                      Bản thu #{rev.revision_number}
                    </span>
                    <span className="text-[10px] text-slate-500">
                      {new Date(rev.created_at).toLocaleString('vi-VN')}
                    </span>
                  </div>
                  <p className="text-slate-300 italic line-clamp-2">&quot;{rev.text}&quot;</p>
                  <div className="flex items-center justify-between pt-1 border-t border-slate-800/60">
                    <span className="text-[11px] text-slate-500 font-mono">
                      {rev.duration_seconds.toFixed(2)}s • {rev.sample_rate}Hz
                    </span>
                    <button
                      onClick={() => handlePlayAudio(rev.id, rev.artifact_id)}
                      className="flex items-center space-x-1 px-2.5 py-1 bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 rounded text-xs font-medium"
                    >
                      <Volume2 className="w-3 h-3" />
                      <span>Nghe bản này</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-800">
              <button
                onClick={() => setActiveRevisionSegment(null)}
                className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white"
              >
                Đóng
              </button>
            </div>
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
