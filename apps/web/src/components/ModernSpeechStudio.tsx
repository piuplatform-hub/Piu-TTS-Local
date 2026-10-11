import React, { useState, useEffect, useRef } from 'react';
import {
  Mic2,
  Sliders,
  Sparkles,
  RotateCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  XCircle,
  Radio,
  FileAudio,
  Download,
  Trash2,
  ChevronDown,
  ChevronUp,
  BookmarkPlus,
  Upload,
  RefreshCw,
} from 'lucide-react';
import { api, ApiError } from '../api/client';
import {
  EngineInfo,
  JobRecord,
  EngineCapabilityDetail,
  VoiceProfile,
} from '../types';
import { AudioPlayer } from './AudioPlayer';

const ACTIVE_JOB_KEY = 'active_studio_job_id';

const SAMPLE_PROMPTS = [
  {
    label: 'Chào mừng',
    lang: 'vi',
    engineHint: 'vieneu-tts',
    text: 'Chào mừng bạn đến với AI Voice Studio. Đây là nền tảng xử lý và tổng hợp giọng nói AI chuyên nghiệp chạy hoàn toàn cục bộ trên máy tính của bạn.',
  },
  {
    label: 'Tin tức',
    lang: 'vi',
    engineHint: 'vieneu-tts',
    text: 'Hôm nay thời tiết tại thủ đô Hà Nội và các tỉnh phía Bắc duy trì trạng thái nhiều mây, độ ẩm cao và có sương mù nhẹ vào sáng sớm.',
  },
  {
    label: 'Kể chuyện',
    lang: 'vi',
    engineHint: 'vieneu-tts',
    text: 'Đêm đã khuya, tiếng mưa rơi đều đều trên mái ngói cũ. Trong gian phòng nhỏ, ánh đèn dầu leo lét soi bóng người thương nhân đang trầm ngâm suy tính.',
  },
  {
    label: 'Quảng cáo',
    lang: 'vi',
    engineHint: 'vieneu-tts',
    text: 'Trải nghiệm công nghệ âm thanh vượt trội cùng sản phẩm mới nhất hôm nay. Đăng ký ngay để nhận ưu đãi đặc biệt!',
  },
  {
    label: 'Tiếng Trung (Qwen3)',
    lang: 'zh',
    engineHint: 'qwen3-tts',
    text: '你好，欢迎使用 AI Voice Studio 本地多模型语音合成系统。',
  },
];

export const ModernSpeechStudio: React.FC = () => {
  // Engines & Capabilities
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [selectedEngineId, setSelectedEngineId] = useState<string>('vieneu-tts');
  const [selectedLang, setSelectedLang] = useState<string>('vi');
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>('hai_dang');
  const [text, setText] = useState<string>(SAMPLE_PROMPTS[0].text);
  const [capabilityDetail, setCapabilityDetail] = useState<EngineCapabilityDetail | null>(null);

  // Sampling & DSP Controls
  const [speed, setSpeed] = useState<number>(1.0);
  const [temperature, setTemperature] = useState<number>(0.8);
  const [topP, setTopP] = useState<number>(0.95);
  const [topK, setTopK] = useState<number>(25);
  const [repetitionPenalty, setRepetitionPenalty] = useState<number>(1.2);
  const [activePresetId, setActivePresetId] = useState<string>('natural_default');
  const [showAdvancedControls, setShowAdvancedControls] = useState<boolean>(false);

  // Voice Cloning & Profiles
  const [synthesisMode, setSynthesisMode] = useState<'preset' | 'clone'>('preset');
  const [refAudioFile, setRefAudioFile] = useState<File | null>(null);
  const [previewAudioUrl, setPreviewAudioUrl] = useState<string | null>(null);
  const [uploadedAssetId, setUploadedAssetId] = useState<string>('');
  const [voiceConsent, setVoiceConsent] = useState<boolean>(false);
  const [denoiseRef, setDenoiseRef] = useState<boolean>(true);
  const [voiceProfiles, setVoiceProfiles] = useState<VoiceProfile[]>([]);
  const [newProfileName, setNewProfileName] = useState<string>('');
  const [showProfileModal, setShowProfileModal] = useState<boolean>(false);

  // Jobs, Execution & History
  const [loadingEngines, setLoadingEngines] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [currentJob, setCurrentJob] = useState<JobRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recentJobs, setRecentJobs] = useState<JobRecord[]>([]);
  const [loadingRecentJobs, setLoadingRecentJobs] = useState<boolean>(false);

  const sseCleanupRef = useRef<(() => void) | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Load Engines
  useEffect(() => {
    let isMounted = true;
    setLoadingEngines(true);

    api.getEngines()
      .then((data) => {
        if (!isMounted) return;
        setEngines(data);
        if (data.length > 0) {
          const defaultEng = data.find((e) => e.id === 'vieneu-tts') || data[0];
          setSelectedEngineId(defaultEng.id);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err instanceof ApiError ? err.problem.detail || err.message : 'Không thể tải danh sách AI Engine.');
      })
      .finally(() => {
        if (isMounted) setLoadingEngines(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Load Capability Details when Engine changes
  useEffect(() => {
    if (!selectedEngineId) return;

    api.getEngineCapabilities(selectedEngineId)
      .then((detail) => {
        setCapabilityDetail(detail);
        if (detail.presets && detail.presets.length > 0) {
          const defPreset = detail.presets.find((p) => p.id === 'natural_default') || detail.presets[0];
          applyVoicePreset(defPreset.id, detail);
        }
      })
      .catch((err) => {
        console.error('Failed to load capability details for', selectedEngineId, err);
        setCapabilityDetail(null);
      });
  }, [selectedEngineId]);

  // Adjust Voice and Language based on active engine
  const activeEngine = engines.find((e) => e.id === selectedEngineId);
  const supportedLangs = activeEngine?.supported_languages || ['vi'];
  const presetVoices = activeEngine?.preset_voices || [];
  const filteredVoices = presetVoices.filter((v) => v.language === selectedLang);

  useEffect(() => {
    if (!supportedLangs.includes(selectedLang)) {
      setSelectedLang(supportedLangs[0] || 'vi');
    }
  }, [selectedEngineId, supportedLangs, selectedLang]);

  useEffect(() => {
    if (filteredVoices.length > 0) {
      if (!selectedVoiceId || !filteredVoices.some((v) => v.id === selectedVoiceId)) {
        setSelectedVoiceId(filteredVoices[0].id);
      }
    } else {
      setSelectedVoiceId('');
    }
  }, [selectedLang, selectedEngineId, filteredVoices, selectedVoiceId]);

  // Load Voice Profiles
  const loadReferenceData = () => {
    api.listVoiceProfiles()
      .then(setVoiceProfiles)
      .catch((e) => console.error('Failed to load voice profiles', e));
  };

  useEffect(() => {
    loadReferenceData();
    loadRecentJobs();
  }, []);

  const loadRecentJobs = () => {
    setLoadingRecentJobs(true);
    api.listJobs(12, 0)
      .then((jobs) => {
        setRecentJobs(jobs);
      })
      .catch((err) => {
        console.error('Failed to load recent jobs', err);
      })
      .finally(() => {
        setLoadingRecentJobs(false);
      });
  };

  // Resume active job if page reloaded
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
  }, []);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      if (sseCleanupRef.current) {
        sseCleanupRef.current();
      }
    };
  }, []);

  // SSE Job Listener
  const attachJobListener = (jobId: string) => {
    if (sseCleanupRef.current) {
      sseCleanupRef.current();
      sseCleanupRef.current = null;
    }

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
            loadRecentJobs();
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

        if (['completed', 'failed', 'cancelled'].includes(evtType)) {
          api.getJob(jobId).then((fullJob) => {
            setCurrentJob(fullJob);
            loadRecentJobs();
          }).catch(() => {});
        }
      },
      () => {
        // SSE fallback polling
        api.getJob(jobId).then((fullJob) => {
          handleJobUpdate(fullJob);
        }).catch(() => {});
      }
    );

    sseCleanupRef.current = cleanup;
  };

  const handleJobUpdate = (job: JobRecord) => {
    setCurrentJob(job);
    if (['completed', 'failed', 'cancelled'].includes(job.status)) {
      setSubmitting(false);
      localStorage.removeItem(ACTIVE_JOB_KEY);
      if (sseCleanupRef.current) {
        sseCleanupRef.current();
        sseCleanupRef.current = null;
      }
      loadRecentJobs();
    }
  };

  const applyVoicePreset = (presetId: string, detail = capabilityDetail) => {
    setActivePresetId(presetId);
    if (!detail?.presets) return;
    const p = detail.presets.find((x) => x.id === presetId);
    if (!p) return;
    if (typeof p.values.temperature === 'number') setTemperature(p.values.temperature);
    if (typeof p.values.top_p === 'number') setTopP(p.values.top_p);
    if (typeof p.values.top_k === 'number') setTopK(p.values.top_k);
    if (typeof p.values.repetition_penalty === 'number') setRepetitionPenalty(p.values.repetition_penalty);
    if (typeof p.values.speed === 'number') setSpeed(p.values.speed);
    if (typeof p.values.denoise === 'boolean') setDenoiseRef(p.values.denoise);
  };

  const handleFileSelect = (file: File | null) => {
    if (previewAudioUrl) {
      URL.revokeObjectURL(previewAudioUrl);
      setPreviewAudioUrl(null);
    }
    setRefAudioFile(file);
    if (file) {
      const url = URL.createObjectURL(file);
      setPreviewAudioUrl(url);
      setUploadedAssetId('');
    }
  };

  const handleSynthesize = async () => {
    if (!text.trim()) {
      setError('Vui lòng nhập đoạn văn bản cần tạo giọng nói.');
      return;
    }

    const supportsCloning = activeEngine?.capabilities?.includes('voice_cloning') ?? false;

    if (synthesisMode === 'clone' && supportsCloning) {
      if (!uploadedAssetId && !refAudioFile) {
        setError('Vui lòng chọn hoặc tải lên tệp âm thanh WAV mẫu để nhân bản giọng nói.');
        return;
      }
      if (!voiceConsent) {
        setError('Bạn phải xác nhận đã có sự đồng ý hợp pháp của chủ giọng nói (Voice-Use Consent).');
        return;
      }
    }

    setError(null);
    setSubmitting(true);

    let targetAssetId = uploadedAssetId;

    if (synthesisMode === 'clone' && supportsCloning && refAudioFile && !targetAssetId) {
      try {
        const uploadRes = await api.uploadReferenceAudio(refAudioFile, voiceConsent);
        targetAssetId = uploadRes.asset_id;
        setUploadedAssetId(targetAssetId);
        loadReferenceData();
      } catch (upErr: any) {
        setSubmitting(false);
        setError(upErr.message || 'Lỗi tải lên tệp âm thanh mẫu tham chiếu.');
        return;
      }
    }

    const payloadParams: Record<string, any> = {
      speed,
    };

    if (supportsCloning && synthesisMode === 'clone') {
      if (targetAssetId) {
        payloadParams['reference_asset_id'] = targetAssetId;
      }
      payloadParams['denoise'] = denoiseRef;
    }

    if (selectedEngineId === 'vieneu-tts') {
      payloadParams['temperature'] = temperature;
      payloadParams['top_p'] = topP;
      payloadParams['top_k'] = topK;
      payloadParams['repetition_penalty'] = repetitionPenalty;
    }

    const resolvedEngineId = selectedEngineId || activeEngine?.id || 'vieneu-tts';
    const resolvedVoiceId = synthesisMode === 'clone'
      ? (targetAssetId ? `profile:${targetAssetId}` : undefined)
      : (selectedVoiceId || (filteredVoices.length > 0 ? filteredVoices[0].id : 'hai_dang'));

    try {
      const job = await api.submitTTSJob({
        text: text.trim(),
        engine_id: resolvedEngineId,
        language: selectedLang || 'vi',
        voice_id: resolvedVoiceId,
        speed,
        parameters: payloadParams,
      });

      setCurrentJob(job);
      localStorage.setItem(ACTIVE_JOB_KEY, job.id);
      attachJobListener(job.id);
      loadRecentJobs();
    } catch (err: any) {
      setSubmitting(false);
      setError(err instanceof ApiError ? err.problem.detail || err.message : (err.message || 'Lỗi khi gửi tác vụ tạo giọng nói.'));
    }
  };

  const handleCancel = async () => {
    if (!currentJob) return;
    try {
      const updated = await api.cancelJob(currentJob.id);
      handleJobUpdate(updated);
    } catch (err: any) {
      setError(err.message || 'Không thể hủy tác vụ.');
    }
  };

  const handleSaveProfile = async () => {
    if (!newProfileName.trim()) {
      setError('Vui lòng nhập tên cho Hồ sơ Giọng mới.');
      return;
    }
    if (!uploadedAssetId) {
      setError('Cần có tệp âm thanh tham chiếu đã lưu trước khi tạo hồ sơ giọng.');
      return;
    }

    try {
      const newProf = await api.createVoiceProfile({
        name: newProfileName.trim(),
        reference_asset_id: uploadedAssetId,
        engine_id: selectedEngineId,
        parameters: {
          speed,
          temperature,
          top_p: topP,
          top_k: topK,
          repetition_penalty: repetitionPenalty,
          denoise: denoiseRef,
        },
      });
      setVoiceProfiles([newProf, ...voiceProfiles]);
      setNewProfileName('');
      setShowProfileModal(false);
    } catch (err: any) {
      setError(err.message || 'Lỗi khi lưu hồ sơ giọng.');
    }
  };

  const handleSelectProfile = (p: VoiceProfile) => {
    setUploadedAssetId(p.reference_asset_id);
    handleFileSelect(null);
    if (p.parameters) {
      if (typeof p.parameters.speed === 'number') setSpeed(p.parameters.speed);
      if (typeof p.parameters.temperature === 'number') setTemperature(p.parameters.temperature);
      if (typeof p.parameters.top_p === 'number') setTopP(p.parameters.top_p);
      if (typeof p.parameters.top_k === 'number') setTopK(p.parameters.top_k);
      if (typeof p.parameters.repetition_penalty === 'number') setRepetitionPenalty(p.parameters.repetition_penalty);
      if (typeof p.parameters.denoise === 'boolean') setDenoiseRef(p.parameters.denoise);
    }
  };

  // Keyboard shortcut Ctrl+Enter to trigger Generate
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (!submitting) {
          handleSynthesize();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [submitting, text, selectedEngineId, selectedVoiceId, synthesisMode, uploadedAssetId, refAudioFile, voiceConsent, speed, temperature, topP, topK, repetitionPenalty, denoiseRef]);

  const supportsCloning = activeEngine?.capabilities?.includes('voice_cloning') ?? false;

  return (
    <div className="space-y-6 max-w-[1680px] mx-auto select-none">
      {/* -------------------------------------------------------------
          HEADER OF SPEECH STUDIO (Title, Description, Quick Badges)
          ------------------------------------------------------------- */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-800/80 pb-4">
        <div className="space-y-1">
          <div className="flex items-center space-x-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-teal-500/10 border border-teal-500/30 text-teal-400">
              <Mic2 className="h-5 w-5" />
            </div>
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center space-x-2">
              <span>Speech Studio</span>
            </h1>
          </div>
          <p className="text-xs text-slate-400">
            Chuyển văn bản thành giọng nói tự nhiên với AI. Hỗ trợ tiếng Việt, nhiều giọng đọc và tùy chỉnh nâng cao.
          </p>
        </div>

        {/* Quick Engine Status Pill */}
        <div className="flex items-center space-x-2">
          <span className="inline-flex items-center space-x-1.5 rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-300">
            <Radio className="h-3.5 w-3.5 text-teal-400" />
            <span className="font-medium text-slate-200">{activeEngine?.name || 'Đang tải...'}</span>
            <span className="text-[10px] text-slate-500 font-mono">({activeEngine?.version || 'v3.8.3'})</span>
          </span>
        </div>
      </div>

      {/* -------------------------------------------------------------
          TWO-COLUMN MAIN WORKSPACE (Editor & Settings Panel)
          ------------------------------------------------------------- */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* =========================================================
            LEFT / CENTER COLUMN (Editor & Cloning Dropzone) - 8 Cols
            ========================================================= */}
        <div className="lg:col-span-7 xl:col-span-8 space-y-5">
          {/* Editor Container Card */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 shadow-xl overflow-hidden flex flex-col">
            {/* Editor Toolbar Header */}
            <div className="flex flex-wrap items-center justify-between border-b border-slate-800/80 px-4 py-2.5 bg-slate-950/60 gap-2">
              {/* Category / Source Tabs */}
              <div className="flex items-center space-x-1">
                <span className="text-xs font-semibold text-slate-300 px-2 py-1 rounded bg-slate-800/80 border border-slate-700/60">
                  Văn bản
                </span>
                <span className="text-xs text-slate-500 px-2 py-1">
                  Nhập tự do
                </span>
              </div>

              {/* Character Counter & Actions */}
              <div className="flex items-center space-x-2 text-xs">
                <span className="font-mono text-[11px] text-slate-400">
                  <strong className="text-teal-400">{text.length}</strong> / 3.000 ký tự
                </span>
                <button
                  type="button"
                  onClick={() => setText('')}
                  className="px-2 py-1 text-slate-400 hover:text-red-400 rounded hover:bg-slate-800 transition-colors"
                  title="Xóa trắng văn bản"
                >
                  Xóa
                </button>
              </div>
            </div>

            {/* Quick Sample Prompts Chips */}
            <div className="px-4 py-2 bg-slate-950/30 border-b border-slate-800/60 flex flex-wrap items-center gap-1.5 text-xs">
              <span className="text-[11px] text-slate-500 mr-1">Mẫu nhanh:</span>
              {SAMPLE_PROMPTS.map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setText(p.text);
                    setSelectedLang(p.lang);
                  }}
                  className="rounded-md border border-slate-800 bg-slate-900 px-2 py-1 text-[11px] text-slate-400 hover:border-teal-500/40 hover:text-teal-300 transition-colors"
                >
                  {p.label}
                </button>
              ))}
            </div>

            {/* Textarea Area */}
            <div className="p-4">
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Nhập đoạn văn bản cần chuyển thành giọng nói tại đây..."
                rows={9}
                className="w-full resize-y rounded-xl border border-slate-800/80 bg-slate-950/80 p-4 font-normal text-sm leading-relaxed text-slate-100 placeholder-slate-600 focus:border-teal-500/60 focus:outline-none focus:ring-1 focus:ring-teal-500/40 transition-all font-sans"
              />
            </div>
          </div>

          {/* Inline Voice Cloning Audio Dropzone Area */}
          {supportsCloning && (
            <div className={`rounded-2xl border p-5 space-y-4 transition-all ${
              synthesisMode === 'clone'
                ? 'border-teal-500/40 bg-slate-900/90 ring-1 ring-teal-500/20'
                : 'border-slate-800 bg-slate-900/50 opacity-90'
            }`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-sm font-semibold text-teal-300">
                  <FileAudio className="h-4 w-4 text-teal-400" />
                  <span>Clone giọng nói từ file mẫu (Reference Voice)</span>
                </div>
                {synthesisMode !== 'clone' && (
                  <button
                    type="button"
                    onClick={() => setSynthesisMode('clone')}
                    className="text-xs text-teal-400 hover:text-teal-300 underline"
                  >
                    Bật chế độ Clone
                  </button>
                )}
              </div>

              <p className="text-xs text-slate-400">
                Tải lên tệp âm thanh WAV (0.5s - 30s) có giọng nói rõ ràng để AI trích xuất vector âm sắc nhân bản giọng đọc.
              </p>

              {/* Upload Dropzone */}
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-800 hover:border-teal-500/40 rounded-xl p-5 text-center cursor-pointer transition-colors bg-slate-950/40 space-y-2"
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  accept=".wav"
                  onChange={(e) => handleFileSelect(e.target.files?.[0] || null)}
                  className="hidden"
                />
                <Upload className="h-6 w-6 text-teal-400 mx-auto" />
                <div className="text-xs text-slate-300">
                  <span className="font-semibold text-teal-400">Nhấp để chọn tệp</span> hoặc kéo thả tệp âm thanh vào đây
                </div>
                <p className="text-[11px] text-slate-500">Định dạng chuẩn: RIFF/WAVE PCM (.wav), tối đa 15MB</p>
              </div>

              {/* Preview Audio File if selected */}
              {refAudioFile && previewAudioUrl && (
                <div className="p-3 rounded-xl bg-slate-950 border border-teal-500/30 flex items-center justify-between">
                  <div className="flex items-center space-x-2.5 truncate">
                    <FileAudio className="h-4 w-4 text-teal-400 shrink-0" />
                    <div className="truncate">
                      <p className="text-xs font-medium text-teal-200 truncate">{refAudioFile.name}</p>
                      <p className="text-[10px] text-slate-500">{(refAudioFile.size / 1024).toFixed(1)} KB</p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <audio controls src={previewAudioUrl} className="h-7 w-48" />
                    <button
                      type="button"
                      onClick={() => handleFileSelect(null)}
                      className="p-1 text-slate-500 hover:text-red-400"
                      title="Hủy tệp này"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              )}

              {/* Existing Reusable Profiles Selection */}
              {voiceProfiles.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-slate-800/80">
                  <label className="text-[11px] font-semibold text-teal-300 flex items-center space-x-1.5">
                    <BookmarkPlus className="h-3.5 w-3.5 text-teal-400" />
                    <span>Hoặc chọn từ Hồ sơ giọng đã lưu (Voice Profiles Library):</span>
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-36 overflow-y-auto pr-1">
                    {voiceProfiles.map((p) => (
                      <div
                        key={p.id}
                        onClick={() => handleSelectProfile(p)}
                        className={`p-2 rounded-lg text-xs flex items-center justify-between cursor-pointer transition-colors ${
                          uploadedAssetId === p.reference_asset_id
                            ? 'bg-teal-900/40 border border-teal-400/60 text-teal-100 ring-1 ring-teal-400/30'
                            : 'bg-slate-950 border border-slate-800 text-slate-300 hover:bg-slate-800/60'
                        }`}
                      >
                        <div className="truncate mr-2">
                          <p className="font-semibold truncate text-teal-300">{p.name}</p>
                          <p className="text-[10px] text-slate-500">
                            Tốc độ: {p.parameters?.speed ?? 1.0}x
                          </p>
                        </div>
                        <span className="text-[10px] font-mono text-teal-400">Chọn</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Save Current as Profile Button */}
              {uploadedAssetId && (
                <div className="pt-1">
                  {!showProfileModal ? (
                    <button
                      type="button"
                      onClick={() => setShowProfileModal(true)}
                      className="flex items-center space-x-1.5 text-xs text-teal-400 hover:text-teal-300 underline"
                    >
                      <BookmarkPlus className="h-3.5 w-3.5" />
                      <span>Lưu mẫu & tham số hiện tại thành Hồ sơ Giọng mới</span>
                    </button>
                  ) : (
                    <div className="p-3 bg-slate-950 rounded-xl border border-teal-500/40 space-y-2">
                      <label className="text-xs font-medium text-teal-300">Tên hồ sơ giọng mới:</label>
                      <input
                        type="text"
                        value={newProfileName}
                        onChange={(e) => setNewProfileName(e.target.value)}
                        placeholder="Ví dụ: Giọng Thuyết Minh Nam A"
                        className="w-full text-xs rounded-lg bg-slate-900 border border-slate-700 px-3 py-1.5 text-white placeholder-slate-500 focus:outline-none focus:border-teal-400"
                      />
                      <div className="flex justify-end space-x-2 pt-1">
                        <button
                          type="button"
                          onClick={() => setShowProfileModal(false)}
                          className="px-2.5 py-1 text-xs text-slate-400 hover:text-white"
                        >
                          Hủy
                        </button>
                        <button
                          type="button"
                          onClick={handleSaveProfile}
                          disabled={!newProfileName.trim()}
                          className="px-3 py-1 text-xs rounded bg-teal-600 hover:bg-teal-500 text-white disabled:opacity-50"
                        >
                          Lưu hồ sơ
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Legal Voice-Use Consent Checkbox */}
              <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 space-y-2 text-xs">
                <label className="flex items-start space-x-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={voiceConsent}
                    onChange={(e) => setVoiceConsent(e.target.checked)}
                    className="mt-0.5 rounded bg-slate-900 border-slate-700 text-teal-600 focus:ring-0"
                  />
                  <span className="text-amber-200 font-medium leading-relaxed">
                    Tôi xác nhận đã có sự đồng ý hợp pháp của chủ giọng nói để sử dụng cho mục đích nhân bản giọng đọc (Voice-Use Consent).
                  </span>
                </label>

                <label className="flex items-center space-x-2 cursor-pointer pt-1 border-t border-amber-500/20 text-slate-300 text-[11px]">
                  <input
                    type="checkbox"
                    checked={denoiseRef}
                    onChange={(e) => setDenoiseRef(e.target.checked)}
                    className="rounded bg-slate-900 border-slate-700 text-teal-600 focus:ring-0"
                  />
                  <span>Tự động khử nhiều tạp âm nền từ file mẫu trước khi trích xuất vector âm sắc</span>
                </label>
              </div>
            </div>
          )}
        </div>

        {/* =========================================================
            RIGHT COLUMN (Settings & Controls Panel) - 4 / 5 Cols
            ========================================================= */}
        <div className="lg:col-span-5 xl:col-span-4 space-y-5">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/90 shadow-xl p-5 space-y-5">
            {/* 1. Engine Selection Card */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                <span>1. Chọn mô hình (Engine):</span>
                <span className="text-[10px] text-teal-400 font-mono">Local-first</span>
              </label>

              <select
                value={selectedEngineId}
                onChange={(e) => setSelectedEngineId(e.target.value)}
                disabled={loadingEngines || submitting}
                className="w-full text-xs font-medium rounded-xl border border-slate-800 bg-slate-950 p-3 text-slate-100 focus:border-teal-500/60 focus:outline-none focus:ring-1 focus:ring-teal-500/40"
              >
                {engines.map((eng) => (
                  <option key={eng.id} value={eng.id}>
                    {eng.name} ({eng.version}) — {eng.device_target.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>

            {/* 2. Synthesis Mode: Preset vs Clone */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300">
                2. Chế độ giọng đọc:
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setSynthesisMode('preset')}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    synthesisMode === 'preset'
                      ? 'border-teal-500/60 bg-teal-500/10 text-teal-200 ring-1 ring-teal-500/30'
                      : 'border-slate-800 bg-slate-950/60 text-slate-400 hover:bg-slate-800/50'
                  }`}
                >
                  <div className="font-semibold text-xs text-white">Giọng có sẵn</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Thư viện giọng chuẩn</div>
                </button>

                <button
                  type="button"
                  disabled={!supportsCloning}
                  onClick={() => setSynthesisMode('clone')}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    synthesisMode === 'clone'
                      ? 'border-teal-500/60 bg-teal-500/10 text-teal-200 ring-1 ring-teal-500/30'
                      : 'border-slate-800 bg-slate-950/60 text-slate-400 hover:bg-slate-800/50'
                  } ${!supportsCloning ? 'opacity-40 cursor-not-allowed' : ''}`}
                >
                  <div className="font-semibold text-xs text-white">Nhân bản (Clone)</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Tạo từ giọng mẫu</div>
                </button>
              </div>
            </div>

            {/* 3. Language & Voice Selection */}
            {synthesisMode === 'preset' && (
              <div className="space-y-4 pt-2 border-t border-slate-800/80">
                {/* Language Select */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">
                    3. Ngôn ngữ:
                  </label>
                  <select
                    value={selectedLang}
                    onChange={(e) => setSelectedLang(e.target.value)}
                    className="w-full text-xs rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200 focus:outline-none focus:border-teal-500"
                  >
                    <option value="vi">Tiếng Việt (vi)</option>
                    {supportedLangs.includes('zh') && <option value="zh">Tiếng Trung (zh)</option>}
                    {supportedLangs.includes('en') && <option value="en">Tiếng Anh (en)</option>}
                  </select>
                </div>

                {/* Preset Voice Select */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">
                    4. Giọng đọc:
                  </label>
                  <select
                    value={selectedVoiceId}
                    onChange={(e) => setSelectedVoiceId(e.target.value)}
                    className="w-full text-xs rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200 focus:outline-none focus:border-teal-500 font-medium"
                  >
                    {filteredVoices.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name} ({v.gender === 'male' ? 'Nam' : 'Nữ'})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            {/* Speaking Speed Slider (DSP Time-stretch) */}
            <div className="space-y-2 pt-2 border-t border-slate-800/80">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-300">Tốc độ nói (Speed):</span>
                <span className="font-mono text-teal-400 font-medium">{speed.toFixed(2)}x</span>
              </div>
              <input
                type="range"
                min={0.5}
                max={2.0}
                step={0.05}
                value={speed}
                onChange={(e) => setSpeed(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-teal-500"
              />
              <div className="flex justify-between text-[10px] text-slate-500">
                <span>0.5x (Chậm)</span>
                <span>1.0x (Chuẩn)</span>
                <span>2.0x (Nhanh)</span>
              </div>
            </div>

            {/* Presets / Reading Styles */}
            {capabilityDetail?.presets && capabilityDetail.presets.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-slate-800/80">
                <label className="text-xs font-semibold text-slate-300">
                  Phong cách đọc (Presets):
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {capabilityDetail.presets.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => applyVoicePreset(p.id)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all ${
                        activePresetId === p.id
                          ? 'border-teal-500/50 bg-teal-500/15 text-teal-300'
                          : 'border-slate-800 bg-slate-950 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Advanced Sampling Parameters (Collapsible) */}
            {selectedEngineId === 'vieneu-tts' && (
              <div className="pt-2 border-t border-slate-800/80">
                <button
                  type="button"
                  onClick={() => setShowAdvancedControls(!showAdvancedControls)}
                  className="w-full flex items-center justify-between text-xs text-slate-400 hover:text-slate-200 py-1"
                >
                  <span className="flex items-center space-x-1.5">
                    <Sliders className="h-3.5 w-3.5 text-teal-400" />
                    <span>Tham số suy luận nâng cao</span>
                  </span>
                  {showAdvancedControls ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </button>

                {showAdvancedControls && (
                  <div className="space-y-3 pt-3 text-xs">
                    <div>
                      <div className="flex justify-between text-slate-400">
                        <span>Temperature (Độ đa dạng):</span>
                        <span className="font-mono text-teal-300">{temperature.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min={0.1}
                        max={1.5}
                        step={0.05}
                        value={temperature}
                        onChange={(e) => setTemperature(parseFloat(e.target.value))}
                        className="w-full h-1 bg-slate-800 rounded accent-teal-500"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-slate-400">
                        <span>Top-P (Nucleus Sampling):</span>
                        <span className="font-mono text-teal-300">{topP.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min={0.1}
                        max={1.0}
                        step={0.05}
                        value={topP}
                        onChange={(e) => setTopP(parseFloat(e.target.value))}
                        className="w-full h-1 bg-slate-800 rounded accent-teal-500"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-slate-400">
                        <span>Repetition Penalty (Chống vấp):</span>
                        <span className="font-mono text-teal-300">{repetitionPenalty.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min={1.0}
                        max={2.5}
                        step={0.05}
                        value={repetitionPenalty}
                        onChange={(e) => setRepetitionPenalty(parseFloat(e.target.value))}
                        className="w-full h-1 bg-slate-800 rounded accent-teal-500"
                      />
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Primary Action Button (CTA) */}
            <div className="pt-2">
              <button
                type="button"
                onClick={handleSynthesize}
                disabled={submitting}
                className="w-full py-3.5 px-4 rounded-xl font-semibold text-sm text-slate-950 bg-gradient-to-r from-teal-400 to-emerald-400 hover:from-teal-300 hover:to-emerald-300 shadow-lg shadow-teal-950/40 disabled:opacity-50 transition-all flex items-center justify-center space-x-2"
              >
                {submitting ? (
                  <>
                    <RotateCw className="h-4 w-4 animate-spin text-slate-950" />
                    <span>Đang tổng hợp giọng nói...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4 text-slate-950" />
                    <span>Tạo giọng nói AI</span>
                    <span className="text-[11px] font-mono text-slate-800 opacity-80 pl-1">(Ctrl + Enter)</span>
                  </>
                )}
              </button>
            </div>

            {/* Error Notification */}
            {error && (
              <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-start space-x-2">
                <AlertTriangle className="h-4 w-4 shrink-0 text-red-400 mt-0.5" />
                <span className="leading-relaxed">{error}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* -------------------------------------------------------------
          ACTIVE JOB PROGRESS & AUDIO PLAYER CARD
          ------------------------------------------------------------- */}
      {currentJob && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
            <div className="flex items-center space-x-2.5">
              {currentJob.status === 'completed' && <CheckCircle2 className="h-5 w-5 text-emerald-400" />}
              {currentJob.status === 'running' && <RotateCw className="h-5 w-5 text-teal-400 animate-spin" />}
              {currentJob.status === 'preparing' && <RotateCw className="h-5 w-5 text-teal-400 animate-spin" />}
              {currentJob.status === 'queued' && <Clock className="h-5 w-5 text-amber-400" />}
              {currentJob.status === 'failed' && <AlertTriangle className="h-5 w-5 text-red-400" />}
              {currentJob.status === 'cancelled' && <XCircle className="h-5 w-5 text-slate-400" />}
              <div>
                <h3 className="text-sm font-semibold text-white flex items-center space-x-2">
                  <span>Trạng thái:</span>
                  <span className="uppercase text-teal-400">{currentJob.status}</span>
                </h3>
                <span className="text-[11px] font-mono text-slate-500">ID: {currentJob.id}</span>
              </div>
            </div>

            {['queued', 'preparing', 'running'].includes(currentJob.status) && (
              <button
                type="button"
                onClick={handleCancel}
                className="px-3 py-1 rounded-lg border border-red-500/30 text-xs text-red-400 hover:bg-red-500/10 transition-colors"
              >
                Hủy tác vụ
              </button>
            )}
          </div>

          {/* Progress Bar */}
          <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800">
            <div
              className={`h-full transition-all duration-300 ${
                currentJob.status === 'completed'
                  ? 'bg-emerald-400'
                  : currentJob.status === 'failed'
                  ? 'bg-red-400'
                  : 'bg-teal-400'
              }`}
              style={{ width: `${currentJob.progress_percent}%` }}
            />
          </div>

          {/* Result Player if completed */}
          {currentJob.status === 'completed' && currentJob.artifact_id && (
            <div className="pt-2">
              <AudioPlayer artifactId={currentJob.artifact_id} />
            </div>
          )}
        </div>
      )}

      {/* -------------------------------------------------------------
          RESULTS & HISTORY TABLE (Full-width Bottom Table)
          ------------------------------------------------------------- */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/90 shadow-xl overflow-hidden space-y-4 p-5">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
          <div className="flex items-center space-x-2">
            <Clock className="h-4 w-4 text-teal-400" />
            <h3 className="text-sm font-bold text-white">Kết quả tạo giọng gần đây</h3>
            <span className="text-[11px] font-mono text-slate-500">({recentJobs.length} bản ghi)</span>
          </div>

          <button
            type="button"
            onClick={loadRecentJobs}
            className="flex items-center space-x-1 text-xs text-slate-400 hover:text-teal-300"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Làm mới</span>
          </button>
        </div>

        {loadingRecentJobs ? (
          <div className="text-center py-6 text-xs text-slate-500">Đang tải lịch sử tạo giọng...</div>
        ) : recentJobs.length === 0 ? (
          <div className="text-center py-8 text-xs text-slate-500">Chưa có bản ghi nào được tạo trong phiên này.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950/60 text-[11px] font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Thời gian</th>
                  <th className="py-2.5 px-3">Mô hình</th>
                  <th className="py-2.5 px-3">Trạng thái</th>
                  <th className="py-2.5 px-3">Tác vụ & Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {recentJobs.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-2.5 px-3 font-mono text-slate-400 text-[11px]">
                      {new Date(job.queued_at).toLocaleTimeString()}
                    </td>
                    <td className="py-2.5 px-3 font-medium text-slate-200">
                      {job.engine_id}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        job.status === 'completed'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : job.status === 'failed'
                          ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                          : 'bg-teal-500/10 text-teal-300 border border-teal-500/20'
                      }`}>
                        <span>{job.status}</span>
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      {job.status === 'completed' && job.artifact_id && (
                        <button
                          type="button"
                          onClick={() => api.downloadArtifactAudio(job.artifact_id!)}
                          className="inline-flex items-center space-x-1 text-teal-400 hover:text-teal-300 text-xs font-medium"
                        >
                          <Download className="h-3.5 w-3.5" />
                          <span>Tải WAV</span>
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
