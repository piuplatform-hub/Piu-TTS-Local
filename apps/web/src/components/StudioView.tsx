import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  Sliders,
  Cpu,
  Languages,
  UserCheck,
  RotateCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  XCircle,
  RefreshCw,
  Radio,
} from 'lucide-react';
import { api, ApiError } from '../api/client';
import { EngineInfo, JobRecord } from '../types';
import { AudioPlayer } from './AudioPlayer';

const ACTIVE_JOB_KEY = 'active_studio_job_id';

const SAMPLE_PROMPTS = [
  {
    label: 'Tiếng Việt - Chào mừng',
    lang: 'vi',
    text: 'Chào mừng bạn đến với AI Voice Studio. Đây là nền tảng xử lý và tổng hợp giọng nói AI chuyên nghiệp chạy hoàn toàn cục bộ trên máy tính của bạn.',
  },
  {
    label: 'Tiếng Việt - Tin tức',
    lang: 'vi',
    text: 'Hôm nay thời tiết tại thủ đô Hà Nội và các tỉnh phía Bắc duy trì trạng thái nhiều mây, độ ẩm cao và có sương mù nhẹ vào sáng sớm.',
  },
  {
    label: 'Tiếng Trung - Chào hỏi',
    lang: 'zh',
    text: '你好，欢迎使用 AI Voice Studio 本地语音合成系统。',
  },
  {
    label: 'English - Welcome',
    lang: 'en',
    text: 'Welcome to AI Voice Studio, an open modular speech synthesis platform running offline.',
  },
];

export const StudioView: React.FC = () => {
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [selectedEngineId, setSelectedEngineId] = useState<string>('');
  const [selectedLang, setSelectedLang] = useState<string>('vi');
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>('');
  const [speed, setSpeed] = useState<number>(1.0);
  const [text, setText] = useState<string>(SAMPLE_PROMPTS[0].text);

  const [loadingEngines, setLoadingEngines] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [currentJob, setCurrentJob] = useState<JobRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sseConnected, setSseConnected] = useState<boolean>(false);

  const sseCleanupRef = useRef<(() => void) | null>(null);

  // Resume active job across page reload
  useEffect(() => {
    const savedJobId = localStorage.getItem(ACTIVE_JOB_KEY);
    if (savedJobId) {
      api.getJob(savedJobId)
        .then((job) => {
          setCurrentJob(job);
          if (['queued', 'preparing', 'running'].includes(job.status)) {
            setSubmitting(true);
            attachJobListener(job.id);
          } else {
            localStorage.removeItem(ACTIVE_JOB_KEY);
          }
        })
        .catch(() => {
          localStorage.removeItem(ACTIVE_JOB_KEY);
        });
    }

    return () => {
      if (sseCleanupRef.current) {
        sseCleanupRef.current();
        sseCleanupRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    // Load available engines
    api.getEngines()
      .then((engs) => {
        setEngines(engs);
        if (engs.length > 0) {
          const first = engs[0];
          setSelectedEngineId(first.id);
          const lang = first.supported_languages[0] || 'vi';
          setSelectedLang(lang);
          const voice = first.preset_voices.find((v) => v.language === lang);
          if (voice) setSelectedVoiceId(voice.id);
        }
      })
      .catch((err) => {
        console.error('Failed to load engines', err);
        setError('Không thể tải danh sách AI Engine từ backend.');
      })
      .finally(() => setLoadingEngines(false));
  }, []);

  // Update available voices when engine or language changes
  const activeEngine = engines.find((e) => e.id === selectedEngineId);
  const filteredVoices = activeEngine?.preset_voices.filter((v) => v.language === selectedLang) || [];

  useEffect(() => {
    if (filteredVoices.length > 0 && !filteredVoices.some((v) => v.id === selectedVoiceId)) {
      setSelectedVoiceId(filteredVoices[0].id);
    }
  }, [selectedLang, selectedEngineId, filteredVoices, selectedVoiceId]);

  const attachJobListener = (jobId: string) => {
    if (sseCleanupRef.current) {
      sseCleanupRef.current();
      sseCleanupRef.current = null;
    }

    setSseConnected(true);

    const cleanup = api.connectJobEvents(
      jobId,
      (evt) => {
        const evtType = evt.event_type;
        const data = evt.data || {};

        setCurrentJob((prev) => {
          if (!prev) return null;
          const updated: JobRecord = { ...prev };

          if (evtType === 'status_change') {
            updated.status = data.status || updated.status;
            if (data.attempt_count !== undefined) updated.attempt_count = data.attempt_count;
            if (data.waiting_reason !== undefined) updated.waiting_reason = data.waiting_reason;
          } else if (evtType === 'progress') {
            if (data.progress_percent !== undefined) updated.progress_percent = data.progress_percent;
            if (data.status) updated.status = data.status;
          } else if (evtType === 'completed') {
            updated.status = 'completed';
            updated.progress_percent = 100;
            updated.artifact_id = data.artifact_id || updated.artifact_id;
            updated.finished_at = data.finished_at || new Date().toISOString();
            setSubmitting(false);
            localStorage.removeItem(ACTIVE_JOB_KEY);
          } else if (evtType === 'failed') {
            updated.status = 'failed';
            updated.error_details = data.error_details || updated.error_details;
            updated.finished_at = data.finished_at || new Date().toISOString();
            setSubmitting(false);
            localStorage.removeItem(ACTIVE_JOB_KEY);
          } else if (evtType === 'cancelled') {
            updated.status = 'cancelled';
            updated.finished_at = data.finished_at || new Date().toISOString();
            setSubmitting(false);
            localStorage.removeItem(ACTIVE_JOB_KEY);
          }

          return updated;
        });

        // Also fetch full sync if terminal
        if (['completed', 'failed', 'cancelled'].includes(evtType)) {
          api.getJob(jobId).then(setCurrentJob).catch(() => {});
        }
      },
      () => {
        setSseConnected(false);
      }
    );

    sseCleanupRef.current = cleanup;
  };

  const handleGenerate = async () => {
    if (!text.trim()) {
      setError('Vui lòng nhập nội dung văn bản cần chuyển đổi.');
      return;
    }
    setError(null);
    setSubmitting(true);

    try {
      const job = await api.submitTTSJob({
        text: text.trim(),
        engine_id: selectedEngineId,
        language: selectedLang,
        voice_id: selectedVoiceId || undefined,
        speed,
        idempotency_key: `client-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      });
      setCurrentJob(job);
      localStorage.setItem(ACTIVE_JOB_KEY, job.id);
      attachJobListener(job.id);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.problem.detail || err.problem.title || 'Lỗi gửi yêu cầu tạo âm thanh');
      } else {
        setError('Lỗi kết nối máy chủ khi tạo âm thanh.');
      }
      setSubmitting(false);
    }
  };

  const handleCancel = async () => {
    if (!currentJob) return;
    if (!window.confirm('Bạn có chắc chắn muốn hủy tác vụ đang xử lý?')) return;

    try {
      const cancelled = await api.cancelJob(currentJob.id);
      setCurrentJob(cancelled);
      setSubmitting(false);
      localStorage.removeItem(ACTIVE_JOB_KEY);
    } catch (err) {
      console.error('Failed to cancel job', err);
    }
  };

  const handleRetry = async () => {
    if (!currentJob) return;
    setError(null);
    setSubmitting(true);

    try {
      const retried = await api.retryJob(currentJob.id);
      setCurrentJob(retried);
      localStorage.setItem(ACTIVE_JOB_KEY, retried.id);
      attachJobListener(retried.id);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.problem.detail || 'Không thể thử lại tác vụ.');
      }
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Title & Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center space-x-2.5">
            <span>Speech Studio</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
              Phase 2 Durable Queue
            </span>
            {sseConnected && (
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center space-x-1 font-mono">
                <Radio className="w-3 h-3 animate-pulse" />
                <span>SSE Live</span>
              </span>
            )}
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Hàng đợi bền vững giao dịch SQLite WAL, cơ chế Fencing Token và tự khôi phục sau sự cố.
          </p>
        </div>

        {activeEngine && (
          <div className="flex items-center space-x-2 text-xs text-slate-400 bg-slate-900 border border-slate-800 px-3.5 py-2 rounded-xl">
            <Cpu className="w-4 h-4 text-emerald-400" />
            <span>Target: <strong className="text-slate-200 uppercase">{activeEngine.device_target}</strong></span>
            <span className="text-slate-700">|</span>
            <span>Version: <strong className="text-slate-200">{activeEngine.version}</strong></span>
          </div>
        )}
      </div>

      {/* Main Studio Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Input text & Quick presets */}
        <div className="lg:col-span-2 space-y-5">
          {/* Quick Prompts */}
          <div className="flex items-center space-x-2 overflow-x-auto pb-1 text-xs">
            <span className="text-slate-500 flex-shrink-0 font-medium">Mẫu:</span>
            {SAMPLE_PROMPTS.map((p, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setText(p.text);
                  setSelectedLang(p.lang);
                }}
                className="px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 hover:border-slate-700 whitespace-nowrap transition-colors"
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Text Area */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3 relative">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span className="font-medium">Nội dung văn bản (Text to Synthesize)</span>
              <span>{text.length} ký tự</span>
            </div>
            <textarea
              rows={8}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Nhập đoạn văn bản cần chuyển thành giọng nói tại đây..."
              className="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors resize-y leading-relaxed"
            />
          </div>

          {/* Action Trigger */}
          <button
            onClick={handleGenerate}
            disabled={submitting || loadingEngines}
            className="w-full py-3.5 px-6 rounded-2xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 active:from-emerald-700 active:to-teal-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium shadow-xl shadow-emerald-950/40 flex items-center justify-center space-x-2.5 text-sm transition-all"
          >
            {submitting ? (
              <>
                <RotateCw className="w-4 h-4 animate-spin" />
                <span>Đang xếp hàng & xử lý âm thanh...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>Tạo giọng nói (Synthesize Speech)</span>
              </>
            )}
          </button>

          {/* Error Banner */}
          {error && (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-start space-x-3">
              <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <div>
                <p className="font-medium">Yêu cầu không thể thực hiện</p>
                <p className="mt-0.5 text-red-400/90">{error}</p>
              </div>
            </div>
          )}

          {/* Real-time Job Progress Card */}
          {currentJob && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2.5">
                  {currentJob.status === 'completed' && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
                  {currentJob.status === 'running' && <RotateCw className="w-5 h-5 text-emerald-400 animate-spin" />}
                  {currentJob.status === 'preparing' && <RotateCw className="w-5 h-5 text-teal-400 animate-spin" />}
                  {currentJob.status === 'queued' && <Clock className="w-5 h-5 text-amber-400" />}
                  {currentJob.status === 'failed' && <AlertTriangle className="w-5 h-5 text-red-400" />}
                  {currentJob.status === 'cancelled' && <XCircle className="w-5 h-5 text-slate-400" />}
                  <div>
                    <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
                      <span>Trạng thái:</span>
                      <span className="uppercase text-emerald-400">{currentJob.status}</span>
                      {currentJob.attempt_count !== undefined && currentJob.attempt_count > 0 && (
                        <span className="text-[10px] text-slate-400 font-normal bg-slate-800 px-2 py-0.5 rounded-full">
                          Lần thử: {currentJob.attempt_count}/{currentJob.max_retries || 3}
                        </span>
                      )}
                    </h3>
                    <p className="text-[11px] text-slate-400 font-mono">ID: {currentJob.id}</p>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  <span className="text-xs font-mono font-medium text-slate-300">
                    {currentJob.progress_percent}%
                  </span>

                  {/* Cancel Button */}
                  {['queued', 'preparing', 'running'].includes(currentJob.status) && (
                    <button
                      onClick={handleCancel}
                      className="px-2.5 py-1 text-xs rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 transition-colors"
                    >
                      Hủy tác vụ
                    </button>
                  )}

                  {/* Retry Button */}
                  {currentJob.status === 'failed' && (
                    <button
                      onClick={handleRetry}
                      className="px-2.5 py-1 text-xs rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 flex items-center space-x-1 transition-colors"
                    >
                      <RefreshCw className="w-3 h-3" />
                      <span>Thử lại</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Waiting reason banner */}
              {currentJob.waiting_reason && ['queued', 'preparing'].includes(currentJob.status) && (
                <div className="p-2.5 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-300 text-xs flex items-center space-x-2">
                  <Clock className="w-3.5 h-3.5 flex-shrink-0 animate-pulse" />
                  <span>{currentJob.waiting_reason}</span>
                </div>
              )}

              {/* Progress bar */}
              <div className="w-full h-2 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                <div
                  className={`h-full transition-all duration-300 rounded-full ${
                    currentJob.status === 'failed'
                      ? 'bg-red-500'
                      : currentJob.status === 'cancelled'
                      ? 'bg-slate-600'
                      : 'bg-gradient-to-r from-emerald-500 to-teal-400'
                  }`}
                  style={{ width: `${currentJob.progress_percent}%` }}
                />
              </div>

              {/* Error details if failed */}
              {currentJob.status === 'failed' && currentJob.error_details && (
                <div className="p-3 bg-red-950/30 border border-red-900/40 rounded-xl text-xs text-red-300">
                  <p className="font-semibold">Mã lỗi: {currentJob.error_details.code || 'UNKNOWN'}</p>
                  <p className="mt-1">{currentJob.error_details.message}</p>
                </div>
              )}

              {/* Audio player if completed */}
              {currentJob.status === 'completed' && currentJob.artifact_id && (
                <div className="pt-2 space-y-3">
                  <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-300 text-xs flex items-center space-x-2">
                    <span className="font-semibold uppercase tracking-wider text-[10px] bg-amber-500/20 px-2 py-0.5 rounded">Contract Test</span>
                    <span>Âm thanh tổng hợp kiểm thử hợp đồng PCM 16-bit. Chưa nạp trọng số AI neural (VieNeu/Qwen3).</span>
                  </div>
                  <AudioPlayer artifactId={currentJob.artifact_id} />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Engine, Voice, Speed Parameters */}
        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
            <div className="flex items-center space-x-2 pb-4 border-b border-slate-800 text-sm font-semibold text-white">
              <Sliders className="w-4 h-4 text-emerald-400" />
              <span>Tham số Cấu hình</span>
            </div>

            {/* Engine Select */}
            <div className="space-y-2">
              <label className="block text-xs font-medium text-slate-300 flex items-center space-x-1.5">
                <Cpu className="w-3.5 h-3.5 text-slate-400" />
                <span>AI Engine</span>
              </label>
              <select
                value={selectedEngineId}
                onChange={(e) => setSelectedEngineId(e.target.value)}
                disabled={loadingEngines || engines.length === 0}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors"
              >
                {engines.map((eng) => (
                  <option key={eng.id} value={eng.id}>
                    {eng.name} ({eng.version})
                  </option>
                ))}
              </select>
            </div>

            {/* Language Select */}
            <div className="space-y-2">
              <label className="block text-xs font-medium text-slate-300 flex items-center space-x-1.5">
                <Languages className="w-3.5 h-3.5 text-slate-400" />
                <span>Ngôn ngữ (Language)</span>
              </label>
              <select
                value={selectedLang}
                onChange={(e) => setSelectedLang(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors"
              >
                {activeEngine?.supported_languages.map((l) => (
                  <option key={l} value={l}>
                    {l === 'vi' ? 'Tiếng Việt (vi)' : l === 'zh' ? 'Tiếng Trung (zh)' : l === 'en' ? 'English (en)' : l}
                  </option>
                ))}
              </select>
            </div>

            {/* Voice Select */}
            <div className="space-y-2">
              <label className="block text-xs font-medium text-slate-300 flex items-center space-x-1.5">
                <UserCheck className="w-3.5 h-3.5 text-slate-400" />
                <span>Giọng đọc (Preset Voice)</span>
              </label>
              <select
                value={selectedVoiceId}
                onChange={(e) => setSelectedVoiceId(e.target.value)}
                disabled={filteredVoices.length === 0}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors"
              >
                {filteredVoices.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name} ({v.gender})
                  </option>
                ))}
              </select>
            </div>

            {/* Speed Slider */}
            <div className="space-y-2 pt-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-slate-300">Tốc độ (Speed)</span>
                <span className="font-mono text-emerald-400 font-semibold">{speed.toFixed(2)}x</span>
              </div>
              <input
                type="range"
                min={0.5}
                max={2.0}
                step={0.05}
                value={speed}
                onChange={(e) => setSpeed(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-slate-950 rounded-lg appearance-none cursor-pointer accent-emerald-500"
              />
              <div className="flex justify-between text-[10px] text-slate-500">
                <span>0.5x (Chậm)</span>
                <span>1.0x (Chuẩn)</span>
                <span>2.0x (Nhanh)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
