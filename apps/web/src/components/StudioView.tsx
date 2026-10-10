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
  Radio,
  Mic,
  FileAudio,
  Zap,
  RotateCcw,
  Volume2,
  Columns,
  Trash2,
  ChevronDown,
  ChevronUp,
  BookmarkPlus,
  Play,
  Info,
} from 'lucide-react';
import { api, ApiError } from '../api/client';
import {
  EngineInfo,
  JobRecord,
  EngineCapabilityDetail,
  ReferenceAsset,
  VoiceProfile,
} from '../types';
import { AudioPlayer } from './AudioPlayer';

const ACTIVE_JOB_KEY = 'active_studio_job_id';

const SAMPLE_PROMPTS = [
  {
    label: 'Tiếng Việt - Chào mừng (VieNeu)',
    lang: 'vi',
    engineHint: 'vieneu-tts',
    text: 'Chào mừng bạn đến với AI Voice Studio. Đây là nền tảng xử lý và tổng hợp giọng nói AI chuyên nghiệp chạy hoàn toàn cục bộ trên máy tính của bạn.',
  },
  {
    label: 'Tiếng Việt - Tin tức (VieNeu)',
    lang: 'vi',
    engineHint: 'vieneu-tts',
    text: 'Hôm nay thời tiết tại thủ đô Hà Nội và các tỉnh phía Bắc duy trì trạng thái nhiều mây, độ ẩm cao và có sương mù nhẹ vào sáng sớm.',
  },
  {
    label: 'Tiếng Việt - Kể chuyện biểu cảm',
    lang: 'vi',
    engineHint: 'vieneu-tts',
    text: 'Đêm đã khuya, tiếng mưa rơi đều đều trên mái ngói cũ. Trong gian phòng nhỏ, ánh đèn dầu leo lét soi bóng người thương nhân đang trầm ngâm suy tính.',
  },
  {
    label: 'Tiếng Trung - Qwen3-TTS (GPU)',
    lang: 'zh',
    engineHint: 'qwen3-tts',
    text: '你好，欢迎使用 AI Voice Studio 本地多模型语音合成系统。',
  },
];

interface ComparisonSlot {
  artifactId: string;
  label: string;
  createdAt: string;
  params: {
    engineId: string;
    voiceOrRef: string;
    speed: number;
    temperature?: number;
    topP?: number;
    topK?: number;
    repetitionPenalty?: number;
    denoise?: boolean;
    presetName?: string;
  };
}

export const StudioView: React.FC = () => {
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [selectedEngineId, setSelectedEngineId] = useState<string>('');
  const [selectedLang, setSelectedLang] = useState<string>('vi');
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>('');
  const [text, setText] = useState<string>(SAMPLE_PROMPTS[0].text);

  // Engine Capabilities Detail
  const [capabilityDetail, setCapabilityDetail] = useState<EngineCapabilityDetail | null>(null);

  // Advanced Voice Controls (Verified Native Sampling Parameters)
  const [speed, setSpeed] = useState<number>(1.0);
  const [temperature, setTemperature] = useState<number>(0.8);
  const [topP, setTopP] = useState<number>(0.95);
  const [topK, setTopK] = useState<number>(25);
  const [repetitionPenalty, setRepetitionPenalty] = useState<number>(1.2);
  const [activePresetId, setActivePresetId] = useState<string>('natural_default');
  const [showAdvancedControls, setShowAdvancedControls] = useState<boolean>(false);

  // Phase 6A: Professional Voice Cloning Studio
  const [synthesisMode, setSynthesisMode] = useState<'preset' | 'clone'>('preset');
  const [refAudioFile, setRefAudioFile] = useState<File | null>(null);
  const [previewAudioUrl, setPreviewAudioUrl] = useState<string | null>(null);
  const [uploadedAssetId, setUploadedAssetId] = useState<string>('');
  const [voiceConsent, setVoiceConsent] = useState<boolean>(false);
  const [denoiseRef, setDenoiseRef] = useState<boolean>(true);
  const [existingAssets, setExistingAssets] = useState<ReferenceAsset[]>([]);
  const [voiceProfiles, setVoiceProfiles] = useState<VoiceProfile[]>([]);
  const [newProfileName, setNewProfileName] = useState<string>('');
  const [showProfileModal, setShowProfileModal] = useState<boolean>(false);

  // A/B Comparison Player Slots
  const [slotA, setSlotA] = useState<ComparisonSlot | null>(null);
  const [slotB, setSlotB] = useState<ComparisonSlot | null>(null);
  const [activeCompareSlot, setActiveCompareSlot] = useState<'A' | 'B'>('A');

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
      if (previewAudioUrl) {
        URL.revokeObjectURL(previewAudioUrl);
      }
    };
  }, []);

  // Load Engines List on mount
  useEffect(() => {
    api.getEngines()
      .then((engs) => {
        setEngines(engs);
        if (engs.length > 0) {
          const preferred = engs.find((e) => e.id === 'vieneu-tts') || engs[0];
          setSelectedEngineId(preferred.id);
          const lang = preferred.supported_languages.includes('vi') ? 'vi' : preferred.supported_languages[0];
          setSelectedLang(lang);
          const voice = preferred.preset_voices.find((v) => v.language === lang) || preferred.preset_voices[0];
          if (voice) setSelectedVoiceId(voice.id);
        }
      })
      .catch((err) => {
        console.error('Failed to load engines', err);
        setError('Không thể tải danh sách AI Engine từ backend.');
      })
      .finally(() => setLoadingEngines(false));
  }, []);

  // Fetch Capability Detail when selectedEngineId changes
  useEffect(() => {
    if (!selectedEngineId) return;
    api.getEngineCapabilities(selectedEngineId)
      .then((cap) => {
        setCapabilityDetail(cap);
        // Apply default preset if available
        if (cap.presets && cap.presets.length > 0) {
          applyPreset(cap.presets[0].id, cap.presets[0].values);
        }
      })
      .catch((err) => {
        console.warn('Failed to fetch capabilities detail for engine', selectedEngineId, err);
        setCapabilityDetail(null);
      });
  }, [selectedEngineId]);

  const activeEngine = engines.find((e) => e.id === selectedEngineId);
  const supportsCloning = activeEngine?.capabilities.includes('voice_cloning') ?? false;
  const supportsAdvancedControls = activeEngine?.capabilities.includes('advanced_voice_controls') ?? false;

  // Handle engine change
  const handleEngineChange = (engineId: string) => {
    setSelectedEngineId(engineId);
    const eng = engines.find((e) => e.id === engineId);
    if (eng) {
      if (!eng.supported_languages.includes(selectedLang)) {
        const nextLang = eng.supported_languages[0] || 'vi';
        setSelectedLang(nextLang);
        const voice = eng.preset_voices.find((v) => v.language === nextLang) || eng.preset_voices[0];
        if (voice) setSelectedVoiceId(voice.id);
      } else {
        const voice = eng.preset_voices.find((v) => v.language === selectedLang) || eng.preset_voices[0];
        if (voice) setSelectedVoiceId(voice.id);
      }
      if (!eng.capabilities.includes('voice_cloning')) {
        setSynthesisMode('preset');
      }
    }
  };

  const filteredVoices = activeEngine?.preset_voices.filter((v) => v.language === selectedLang) || [];

  useEffect(() => {
    if (filteredVoices.length > 0 && !filteredVoices.some((v) => v.id === selectedVoiceId)) {
      setSelectedVoiceId(filteredVoices[0].id);
    }
  }, [selectedLang, selectedEngineId, filteredVoices, selectedVoiceId]);

  // Load existing reference audio assets and voice profiles when in clone mode
  useEffect(() => {
    if (synthesisMode === 'clone') {
      api.listReferenceAudios()
        .then(setExistingAssets)
        .catch((e) => console.error('Failed to load user reference audios', e));
      api.listVoiceProfiles()
        .then(setVoiceProfiles)
        .catch((e) => console.error('Failed to load user voice profiles', e));
    }
  }, [synthesisMode]);

  // Manage Preview Audio URL when refAudioFile changes
  const handleFileSelect = (f: File | null) => {
    if (previewAudioUrl) {
      URL.revokeObjectURL(previewAudioUrl);
      setPreviewAudioUrl(null);
    }
    setRefAudioFile(f);
    if (f) {
      setUploadedAssetId('');
      const url = URL.createObjectURL(f);
      setPreviewAudioUrl(url);
    }
  };

  // Apply a voice preset
  const applyPreset = (presetId: string, values: Record<string, any>) => {
    setActivePresetId(presetId);
    if (values.speed !== undefined) setSpeed(values.speed);
    if (values.temperature !== undefined) setTemperature(values.temperature);
    if (values.top_p !== undefined) setTopP(values.top_p);
    if (values.top_k !== undefined) setTopK(values.top_k);
    if (values.repetition_penalty !== undefined) setRepetitionPenalty(values.repetition_penalty);
    if (values.denoise !== undefined) setDenoiseRef(Boolean(values.denoise));
  };

  const resetToDefaults = () => {
    setSpeed(1.0);
    setTemperature(0.8);
    setTopP(0.95);
    setTopK(25);
    setRepetitionPenalty(1.2);
    setDenoiseRef(true);
    setActivePresetId('natural_default');
  };

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
            const artId = data.artifact_id || updated.artifact_id;
            updated.artifact_id = artId;
            updated.finished_at = data.finished_at || new Date().toISOString();
            setSubmitting(false);
            localStorage.removeItem(ACTIVE_JOB_KEY);

            // Populate Comparison Slots automatically
            if (artId) {
              const newSlot: ComparisonSlot = {
                artifactId: artId,
                label: synthesisMode === 'clone' ? 'Bản Nhân Bản Giọng' : `Giọng ${selectedVoiceId}`,
                createdAt: new Date().toLocaleTimeString(),
                params: {
                  engineId: selectedEngineId,
                  voiceOrRef: synthesisMode === 'clone' ? 'Cloned Reference' : selectedVoiceId,
                  speed,
                  temperature: supportsAdvancedControls ? temperature : undefined,
                },
              };

              setSlotA((currA) => {
                if (!currA) {
                  return newSlot;
                } else {
                  setSlotB(newSlot);
                  return currA;
                }
              });
            }
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

    const parameters: Record<string, any> = {};

    // Native & DSP Parameters
    parameters.speed = speed;
    if (supportsAdvancedControls) {
      parameters.temperature = temperature;
      parameters.top_p = topP;
      parameters.top_k = topK;
      parameters.repetition_penalty = repetitionPenalty;
    }

    if (synthesisMode === 'clone' && supportsCloning) {
      if (!voiceConsent) {
        setError('Bạn phải xác nhận đã có sự đồng ý hợp pháp của chủ giọng nói để nhân bản giọng đọc.');
        return;
      }

      let targetAssetId = uploadedAssetId;

      if (refAudioFile) {
        try {
          const uploadRes = await api.uploadReferenceAudio(refAudioFile, voiceConsent);
          targetAssetId = uploadRes.asset_id;
          setUploadedAssetId(targetAssetId);
          // Refresh existing assets list
          api.listReferenceAudios().then(setExistingAssets).catch(() => {});
        } catch (upErr: any) {
          setError(upErr.message || 'Lỗi tải lên tệp âm thanh mẫu tham chiếu.');
          return;
        }
      } else if (!targetAssetId) {
        setError('Vui lòng chọn hoặc tải lên tệp âm thanh WAV mẫu để nhân bản giọng nói.');
        return;
      }

      parameters.reference_asset_id = targetAssetId;
      parameters.denoise = denoiseRef;
    }

    setError(null);
    setSubmitting(true);

    try {
      const job = await api.submitTTSJob({
        text: text.trim(),
        engine_id: selectedEngineId,
        language: selectedLang,
        voice_id: synthesisMode === 'preset' ? (selectedVoiceId || undefined) : undefined,
        speed,
        parameters,
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

  const handleDeleteAsset = async (assetId: string) => {
    if (!window.confirm('Bạn có chắc muốn xóa tệp mẫu tham chiếu này khỏi thư viện?')) return;
    try {
      await api.deleteReferenceAudio(assetId);
      setExistingAssets((prev) => prev.filter((a) => a.id !== assetId));
      if (uploadedAssetId === assetId) {
        setUploadedAssetId('');
      }
    } catch (err: any) {
      setError(err.message || 'Lỗi khi xóa tệp mẫu tham chiếu.');
    }
  };

  const handlePlayExistingAsset = async (assetId: string) => {
    try {
      const blob = await api.fetchReferenceAudioBlob(assetId);
      const url = URL.createObjectURL(blob);
      if (previewAudioUrl) URL.revokeObjectURL(previewAudioUrl);
      setPreviewAudioUrl(url);
    } catch (err: any) {
      setError('Không thể phát âm thanh mẫu từ máy chủ.');
    }
  };

  const handleSaveProfile = async () => {
    if (!newProfileName.trim() || !uploadedAssetId) return;
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
    setActivePresetId('custom');
  };

  const handleDeleteProfile = async (id: string) => {
    if (!window.confirm('Bạn có chắc chắn muốn xóa hồ sơ giọng này?')) return;
    try {
      await api.deleteVoiceProfile(id);
      setVoiceProfiles(voiceProfiles.filter((p) => p.id !== id));
    } catch (err: any) {
      setError(err.message || 'Lỗi khi xóa hồ sơ giọng.');
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Title & Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center space-x-2.5">
            <span>Voice Lab &amp; Speech Studio</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium flex items-center space-x-1">
              <Zap className="w-3 h-3 text-emerald-400" />
              <span>Phase 6A Neural Engine</span>
            </span>
            {sseConnected && (
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center space-x-1 font-mono">
                <Radio className="w-3 h-3 animate-pulse" />
                <span>SSE Live</span>
              </span>
            )}
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Phòng thí nghiệm giọng nói AI: Nhân bản giọng chuẩn xác (Zero-shot Cloning), tinh chỉnh ngữ điệu chuyên sâu &amp; thẩm âm đối chiếu A/B.
          </p>
        </div>

        {activeEngine && (
          <div className="flex items-center space-x-2.5 text-xs text-slate-400 bg-slate-900 border border-slate-800 px-3.5 py-2 rounded-xl">
            <Cpu className="w-4 h-4 text-emerald-400" />
            <span>Đích: <strong className="text-slate-200 uppercase">{activeEngine.device_target}</strong></span>
            <span className="text-slate-700">|</span>
            <span>Mẫu: <strong className="text-slate-200">{activeEngine.id === 'vieneu-tts' ? '48kHz' : activeEngine.id === 'qwen3-tts' ? '24kHz' : '44.1kHz'}</strong></span>
            <span className="text-slate-700">|</span>
            <span>Phiên bản: <strong className="text-slate-200">{activeEngine.version}</strong></span>
          </div>
        )}
      </div>

      {/* Main Studio Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Input text, Action, Real-time status, A/B Player */}
        <div className="lg:col-span-2 space-y-5">
          {/* Quick Prompts */}
          <div className="flex items-center space-x-2 overflow-x-auto pb-1 text-xs">
            <span className="text-slate-500 flex-shrink-0 font-medium">Mẫu câu:</span>
            {SAMPLE_PROMPTS.map((p, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setText(p.text);
                  setSelectedLang(p.lang);
                  if (p.engineHint && engines.some((e) => e.id === p.engineHint)) {
                    handleEngineChange(p.engineHint);
                  }
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
              rows={6}
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
                <span>Đang xếp hàng &amp; tổng hợp âm thanh qua AI Worker...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>
                  {synthesisMode === 'clone'
                    ? 'Nhân bản giọng & Tổng hợp (Synthesize Cloned Speech)'
                    : 'Tạo giọng nói AI (Synthesize Speech)'}
                </span>
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
                    <p className="text-[11px] text-slate-400 font-mono">ID: {currentJob.id} · Engine: {currentJob.engine_id}</p>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  <span className="text-xs font-mono font-medium text-slate-300">
                    {currentJob.progress_percent}%
                  </span>
                  {['queued', 'preparing', 'running'].includes(currentJob.status) && (
                    <button
                      onClick={handleCancel}
                      className="px-2.5 py-1 text-xs rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
                    >
                      Hủy tác vụ
                    </button>
                  )}
                  {['failed', 'cancelled'].includes(currentJob.status) && (
                    <button
                      onClick={handleRetry}
                      disabled={submitting}
                      className="px-2.5 py-1 text-xs rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 transition-colors flex items-center space-x-1"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>Thử lại</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden border border-slate-800/80">
                <div
                  className={`h-full transition-all duration-300 ${
                    currentJob.status === 'failed'
                      ? 'bg-red-500'
                      : currentJob.status === 'cancelled'
                      ? 'bg-slate-600'
                      : 'bg-gradient-to-r from-emerald-500 to-teal-400'
                  }`}
                  style={{ width: `${currentJob.progress_percent}%` }}
                />
              </div>

              {/* Audio Player if completed */}
              {currentJob.status === 'completed' && currentJob.artifact_id && (
                <div className="pt-2 border-t border-slate-800/80 space-y-3">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span className="font-medium text-emerald-400 flex items-center space-x-1.5">
                      <Volume2 className="w-4 h-4" />
                      <span>Tệp âm thanh hoàn tất</span>
                    </span>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => {
                          if (currentJob.artifact_id) {
                            setSlotA({
                              artifactId: currentJob.artifact_id,
                              label: `Bản thu A (${new Date().toLocaleTimeString()})`,
                              createdAt: new Date().toLocaleTimeString(),
                              params: {
                                engineId: selectedEngineId,
                                voiceOrRef: synthesisMode === 'clone' ? (uploadedAssetId ? `Clone (${uploadedAssetId.slice(0, 8)})` : 'Cloned') : (selectedVoiceId || 'Hải Đăng'),
                                speed,
                                temperature: supportsAdvancedControls ? temperature : undefined,
                                topP: supportsAdvancedControls ? topP : undefined,
                                topK: supportsAdvancedControls ? topK : undefined,
                                repetitionPenalty: supportsAdvancedControls ? repetitionPenalty : undefined,
                                denoise: synthesisMode === 'clone' ? denoiseRef : undefined,
                                presetName: activePresetId !== 'custom' ? activePresetId : undefined,
                              },
                            });
                          }
                        }}
                        className="px-2 py-0.5 text-[10px] rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
                      >
                        Lưu vào Slot A
                      </button>
                      <button
                        onClick={() => {
                          if (currentJob.artifact_id) {
                            setSlotB({
                              artifactId: currentJob.artifact_id,
                              label: `Bản thu B (${new Date().toLocaleTimeString()})`,
                              createdAt: new Date().toLocaleTimeString(),
                              params: {
                                engineId: selectedEngineId,
                                voiceOrRef: synthesisMode === 'clone' ? (uploadedAssetId ? `Clone (${uploadedAssetId.slice(0, 8)})` : 'Cloned') : (selectedVoiceId || 'Hải Đăng'),
                                speed,
                                temperature: supportsAdvancedControls ? temperature : undefined,
                                topP: supportsAdvancedControls ? topP : undefined,
                                topK: supportsAdvancedControls ? topK : undefined,
                                repetitionPenalty: supportsAdvancedControls ? repetitionPenalty : undefined,
                                denoise: synthesisMode === 'clone' ? denoiseRef : undefined,
                                presetName: activePresetId !== 'custom' ? activePresetId : undefined,
                              },
                            });
                          }
                        }}
                        className="px-2 py-0.5 text-[10px] rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
                      >
                        Lưu vào Slot B
                      </button>
                    </div>
                  </div>
                  <AudioPlayer artifactId={currentJob.artifact_id} />
                </div>
              )}
            </div>
          )}

          {/* Phase 6A: A/B Comparison Player Panel */}
          {(slotA || slotB) && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center space-x-2">
                  <Columns className="w-4 h-4 text-teal-400" />
                  <h3 className="text-sm font-semibold text-white">Thẩm âm &amp; So sánh A/B (Comparison Player)</h3>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setActiveCompareSlot('A')}
                    className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                      activeCompareSlot === 'A'
                        ? 'bg-emerald-600 text-white shadow'
                        : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Bản A
                  </button>
                  <button
                    onClick={() => setActiveCompareSlot('B')}
                    className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                      activeCompareSlot === 'B'
                        ? 'bg-teal-600 text-white shadow'
                        : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    Bản B
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Slot A Card */}
                <div className={`p-4 rounded-xl border transition-all ${activeCompareSlot === 'A' ? 'bg-emerald-950/20 border-emerald-500/40 ring-1 ring-emerald-500/30' : 'bg-slate-950/60 border-slate-800/80'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">Slot A</span>
                    {slotA && <span className="text-[10px] text-slate-500 font-mono">{slotA.createdAt}</span>}
                  </div>
                  {slotA ? (
                    <div className="space-y-3">
                      <p className="text-xs text-slate-200 font-medium">{slotA.label}</p>
                      <div className="text-[11px] text-slate-400 space-y-0.5 bg-slate-900/60 p-2 rounded-lg border border-slate-800/60">
                        <p>Giọng: <span className="text-slate-300 font-mono">{slotA.params.voiceOrRef}</span></p>
                        <p>Tốc độ (Speed): <span className="text-slate-300 font-mono">{slotA.params.speed}x</span></p>
                        {slotA.params.temperature !== undefined && <p>Độ biến thiên (Temp): <span className="text-slate-300 font-mono">{slotA.params.temperature}</span></p>}
                        {slotA.params.topP !== undefined && <p>Top-P / Top-K: <span className="text-slate-300 font-mono">{slotA.params.topP} / {slotA.params.topK}</span></p>}
                        {slotA.params.repetitionPenalty !== undefined && <p>Chống vấp (Rep. Pen): <span className="text-slate-300 font-mono">{slotA.params.repetitionPenalty}</span></p>}
                        {slotA.params.presetName && <p>Gợi ý: <span className="text-slate-300 font-mono">{slotA.params.presetName}</span></p>}
                      </div>
                      <AudioPlayer artifactId={slotA.artifactId} />
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500 italic py-4 text-center">Chưa có bản thu nào ở Slot A</p>
                  )}
                </div>

                {/* Slot B Card */}
                <div className={`p-4 rounded-xl border transition-all ${activeCompareSlot === 'B' ? 'bg-teal-950/20 border-teal-500/40 ring-1 ring-teal-500/30' : 'bg-slate-950/60 border-slate-800/80'}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-teal-400 uppercase tracking-wider">Slot B</span>
                    {slotB && <span className="text-[10px] text-slate-500 font-mono">{slotB.createdAt}</span>}
                  </div>
                  {slotB ? (
                    <div className="space-y-3">
                      <p className="text-xs text-slate-200 font-medium">{slotB.label}</p>
                      <div className="text-[11px] text-slate-400 space-y-0.5 bg-slate-900/60 p-2 rounded-lg border border-slate-800/60">
                        <p>Giọng: <span className="text-slate-300 font-mono">{slotB.params.voiceOrRef}</span></p>
                        <p>Tốc độ (Speed): <span className="text-slate-300 font-mono">{slotB.params.speed}x</span></p>
                        {slotB.params.temperature !== undefined && <p>Độ biến thiên (Temp): <span className="text-slate-300 font-mono">{slotB.params.temperature}</span></p>}
                        {slotB.params.topP !== undefined && <p>Top-P / Top-K: <span className="text-slate-300 font-mono">{slotB.params.topP} / {slotB.params.topK}</span></p>}
                        {slotB.params.repetitionPenalty !== undefined && <p>Chống vấp (Rep. Pen): <span className="text-slate-300 font-mono">{slotB.params.repetitionPenalty}</span></p>}
                        {slotB.params.presetName && <p>Gợi ý: <span className="text-slate-300 font-mono">{slotB.params.presetName}</span></p>}
                      </div>
                      <AudioPlayer artifactId={slotB.artifactId} />
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500 italic py-4 text-center">Chưa có bản thu nào ở Slot B</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Engine, Voice Mode, Cloning Lab, Advanced Controls, Presets */}
        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
            <div className="flex items-center space-x-2 pb-4 border-b border-slate-800 text-sm font-semibold text-white">
              <Sliders className="w-4 h-4 text-emerald-400" />
              <span>Cấu hình Mô hình &amp; Giọng nói</span>
            </div>

            {/* Engine Select */}
            <div className="space-y-2">
              <label className="block text-xs font-medium text-slate-300 flex items-center space-x-1.5">
                <Cpu className="w-3.5 h-3.5 text-slate-400" />
                <span>AI Engine</span>
              </label>
              <select
                value={selectedEngineId}
                onChange={(e) => handleEngineChange(e.target.value)}
                disabled={loadingEngines || engines.length === 0}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors"
              >
                {engines.map((eng) => (
                  <option key={eng.id} value={eng.id}>
                    {eng.name} ({eng.version}) — {eng.device_target.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>

            {/* Synthesis Mode (Preset Voice vs Voice Cloning) */}
            {supportsCloning && (
              <div className="space-y-2 pt-1">
                <label className="block text-xs font-medium text-slate-300">Chế độ giọng đọc</label>
                <div className="grid grid-cols-2 gap-2 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
                  <button
                    type="button"
                    onClick={() => setSynthesisMode('preset')}
                    className={`py-1.5 px-3 rounded-lg font-medium transition-all flex items-center justify-center space-x-1.5 ${
                      synthesisMode === 'preset'
                        ? 'bg-emerald-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <UserCheck className="w-3.5 h-3.5" />
                    <span>Giọng mẫu (Preset)</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setSynthesisMode('clone')}
                    className={`py-1.5 px-3 rounded-lg font-medium transition-all flex items-center justify-center space-x-1.5 ${
                      synthesisMode === 'clone'
                        ? 'bg-teal-600 text-white shadow-sm'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <Mic className="w-3.5 h-3.5" />
                    <span>Nhân bản (Clone)</span>
                  </button>
                </div>
              </div>
            )}

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

            {/* Mode 1: Preset Voice Select */}
            {synthesisMode === 'preset' ? (
              <div className="space-y-2">
                <label className="block text-xs font-medium text-slate-300 flex items-center space-x-1.5">
                  <UserCheck className="w-3.5 h-3.5 text-slate-400" />
                  <span>Giọng đọc ({filteredVoices.length} giọng tích hợp)</span>
                </label>
                <select
                  value={selectedVoiceId}
                  onChange={(e) => setSelectedVoiceId(e.target.value)}
                  disabled={filteredVoices.length === 0}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors"
                >
                  {filteredVoices.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name} ({v.gender === 'male' ? 'Nam' : v.gender === 'female' ? 'Nữ' : v.gender})
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              /* Mode 2: Voice Cloning Reference Studio */
              <div className="space-y-3 p-4 bg-slate-950/80 border border-teal-500/30 rounded-xl">
                <div className="flex items-center space-x-1.5 text-xs font-semibold text-teal-400">
                  <FileAudio className="w-4 h-4" />
                  <span>Voice Cloning Studio — Mẫu âm thanh tham chiếu</span>
                </div>
                
                <p className="text-[11px] text-slate-400">
                  Tải lên tệp WAV giọng nói mẫu (0.5s - 30s) để AI trích xuất vector âm sắc nhân bản giọng đọc.
                </p>

                <input
                  type="file"
                  accept=".wav"
                  onChange={(e) => handleFileSelect(e.target.files?.[0] || null)}
                  className="block w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-teal-600/20 file:text-teal-300 hover:file:bg-teal-600/30 cursor-pointer"
                />

                {/* Preview Selected Audio */}
                {refAudioFile && previewAudioUrl && (
                  <div className="p-2.5 rounded-lg bg-teal-950/30 border border-teal-500/20 space-y-2">
                    <div className="flex items-center justify-between text-[11px] text-teal-300">
                      <span className="font-mono truncate max-w-[200px]">{refAudioFile.name}</span>
                      <span className="text-[10px] text-slate-400">{(refAudioFile.size / 1024).toFixed(1)} KB</span>
                    </div>
                    <audio controls src={previewAudioUrl} className="w-full h-8" />
                  </div>
                )}

                {/* Voice Profiles (Reusable Voice Library) */}
                {voiceProfiles.length > 0 && (
                  <div className="space-y-1.5 pt-1 border-t border-slate-800/80">
                    <label className="text-[11px] text-teal-300 font-semibold flex items-center space-x-1.5">
                      <BookmarkPlus className="w-3.5 h-3.5 text-teal-400" />
                      <span>Hồ sơ giọng đã lưu (Voice Profiles Library):</span>
                    </label>
                    <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                      {voiceProfiles.map((p) => (
                        <div
                          key={p.id}
                          onClick={() => handleSelectProfile(p)}
                          className={`p-2 rounded-lg text-xs flex items-center justify-between cursor-pointer transition-colors ${
                            uploadedAssetId === p.reference_asset_id
                              ? 'bg-teal-900/50 border border-teal-400/60 text-teal-100 ring-1 ring-teal-400/30'
                              : 'bg-slate-900 border border-slate-800 text-slate-300 hover:bg-slate-800/80'
                          }`}
                        >
                          <div className="truncate mr-2">
                            <p className="font-semibold truncate text-teal-300">{p.name}</p>
                            <p className="text-[10px] text-slate-400">
                              Tốc độ: {p.parameters?.speed ?? 1.0}x · Temp: {p.parameters?.temperature ?? 0.8}
                            </p>
                          </div>
                          <div className="flex items-center space-x-1">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handlePlayExistingAsset(p.reference_asset_id);
                              }}
                              className="p-1 text-slate-400 hover:text-teal-300 transition-colors"
                              title="Nghe thử mẫu"
                            >
                              <Play className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteProfile(p.id);
                              }}
                              className="p-1 text-slate-500 hover:text-red-400 transition-colors"
                              title="Xóa hồ sơ"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Existing Assets Library */}
                {existingAssets.length > 0 && (
                  <div className="space-y-1.5 pt-1 border-t border-slate-800/80">
                    <label className="text-[11px] text-slate-400 font-medium">Hoặc chọn mẫu từ thư viện tệp đã tải lên:</label>
                    <div className="space-y-1 max-h-36 overflow-y-auto pr-1">
                      {existingAssets.map((a) => (
                        <div
                          key={a.id}
                          onClick={() => {
                            setUploadedAssetId(a.id);
                            handleFileSelect(null);
                          }}
                          className={`p-2 rounded-lg text-xs flex items-center justify-between cursor-pointer transition-colors ${
                            uploadedAssetId === a.id
                              ? 'bg-teal-900/40 border border-teal-500/40 text-teal-200'
                              : 'bg-slate-900 border border-slate-800 text-slate-300 hover:bg-slate-800/80'
                          }`}
                        >
                          <div className="truncate mr-2">
                            <p className="font-medium truncate">{a.filename}</p>
                            <p className="text-[10px] text-slate-500">{a.duration_seconds}s · {a.sample_rate}Hz</p>
                          </div>
                          <div className="flex items-center space-x-1">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handlePlayExistingAsset(a.id);
                              }}
                              className="p-1 text-slate-400 hover:text-teal-300 transition-colors"
                              title="Nghe thử mẫu"
                            >
                              <Play className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteAsset(a.id);
                              }}
                              className="p-1 text-slate-500 hover:text-red-400 transition-colors"
                              title="Xóa mẫu"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Save Current as Voice Profile Modal / Button */}
                {uploadedAssetId && (
                  <div className="pt-1">
                    {!showProfileModal ? (
                      <button
                        type="button"
                        onClick={() => setShowProfileModal(true)}
                        className="w-full py-1.5 px-3 rounded-lg bg-teal-950/40 hover:bg-teal-900/40 text-teal-300 border border-teal-500/30 text-xs font-medium flex items-center justify-center space-x-1.5 transition-colors"
                      >
                        <BookmarkPlus className="w-3.5 h-3.5" />
                        <span>Lưu mẫu &amp; tham số hiện tại thành Hồ sơ Giọng</span>
                      </button>
                    ) : (
                      <div className="p-2.5 bg-slate-900 rounded-lg border border-teal-500/40 space-y-2">
                        <label className="text-[11px] font-medium text-teal-300">Tên hồ sơ giọng mới:</label>
                        <input
                          type="text"
                          value={newProfileName}
                          onChange={(e) => setNewProfileName(e.target.value)}
                          placeholder="Ví dụ: Giọng Chị Mai - Đọc Truyện"
                          className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:border-teal-500"
                        />
                        <div className="flex justify-end space-x-2 pt-1">
                          <button
                            type="button"
                            onClick={() => setShowProfileModal(false)}
                            className="px-2.5 py-1 text-[11px] rounded bg-slate-800 text-slate-400 hover:text-slate-200"
                          >
                            Hủy
                          </button>
                          <button
                            type="button"
                            onClick={handleSaveProfile}
                            disabled={!newProfileName.trim()}
                            className="px-3 py-1 text-[11px] rounded bg-teal-600 hover:bg-teal-500 text-white disabled:opacity-50"
                          >
                            Lưu hồ sơ
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Legal Voice-Use Consent Checkbox */}
                <label className="flex items-start space-x-2 text-[11px] text-slate-300 cursor-pointer pt-1 bg-amber-500/10 p-2.5 rounded-lg border border-amber-500/20">
                  <input
                    type="checkbox"
                    checked={voiceConsent}
                    onChange={(e) => setVoiceConsent(e.target.checked)}
                    className="mt-0.5 rounded bg-slate-900 border-slate-700 text-teal-600 focus:ring-0"
                  />
                  <span className="text-amber-300 font-medium leading-relaxed">
                    Tôi xác nhận đã có sự đồng ý hợp pháp của chủ giọng nói để sử dụng cho mục đích nhân bản giọng đọc (Voice-Use Consent)
                  </span>
                </label>

                {/* Denoise Toggle */}
                <label className="flex items-center space-x-2 text-[11px] text-slate-300 cursor-pointer pt-0.5">
                  <input
                    type="checkbox"
                    checked={denoiseRef}
                    onChange={(e) => setDenoiseRef(e.target.checked)}
                    className="rounded bg-slate-900 border-slate-700 text-teal-600 focus:ring-0"
                  />
                  <span>Tự động khử nhiễu tạp âm nền từ file mẫu trước khi trích xuất embedding</span>
                </label>
              </div>
            )}

            {/* Presets Selector */}
            {capabilityDetail?.presets && capabilityDetail.presets.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-xs font-semibold text-slate-300">Cấu hình tham số gợi ý (Recommended Presets)</label>
                    <p className="text-[10px] text-slate-500">Gợi ý tầng ứng dụng (Application Suggestions)</p>
                  </div>
                  <span className="text-[10px] text-emerald-400 font-medium bg-emerald-950/40 border border-emerald-500/30 px-1.5 py-0.5 rounded">Gợi ý</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {capabilityDetail.presets.map((pr) => (
                    <button
                      key={pr.id}
                      type="button"
                      onClick={() => applyPreset(pr.id, pr.values)}
                      className={`p-2 rounded-xl text-left border transition-all ${
                        activePresetId === pr.id
                          ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-200'
                          : 'bg-slate-950 border-slate-800/80 text-slate-400 hover:border-slate-700 hover:text-slate-300'
                      }`}
                    >
                      <p className="text-xs font-medium">{pr.label}</p>
                      <p className="text-[10px] text-slate-500 truncate mt-0.5">{pr.description}</p>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Speed Slider (Always Available) */}
            <div className="space-y-2 pt-2 border-t border-slate-800">
              <div className="flex items-center justify-between text-xs">
                <div>
                  <span className="font-medium text-slate-300">Tốc độ phát âm (Speed)</span>
                  <p className="text-[10px] text-slate-500">DSP phase vocoder (bảo toàn cao độ xấp xỉ)</p>
                </div>
                <span className="font-mono text-emerald-400 font-semibold">{speed.toFixed(2)}x</span>
              </div>
              <input
                type="range"
                min={0.5}
                max={2.0}
                step={0.05}
                value={speed}
                onChange={(e) => {
                  setSpeed(parseFloat(e.target.value));
                  setActivePresetId('custom');
                }}
                className="w-full h-1.5 bg-slate-950 rounded-lg appearance-none cursor-pointer accent-emerald-500"
              />
              <div className="flex justify-between text-[10px] text-slate-500">
                <span>0.5x (Chậm)</span>
                <span>1.0x (Chuẩn)</span>
                <span>2.0x (Nhanh)</span>
              </div>
            </div>

            {/* Advanced Voice Controls Accordion (Native Model Parameters) */}
            {supportsAdvancedControls && (
              <div className="pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAdvancedControls(!showAdvancedControls)}
                  className="w-full flex items-center justify-between text-xs font-semibold text-slate-300 hover:text-emerald-400 transition-colors py-1"
                >
                  <span className="flex items-center space-x-1.5">
                    <Sliders className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Tinh chỉnh giọng nâng cao (Advanced Controls)</span>
                  </span>
                  {showAdvancedControls ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>

                {showAdvancedControls && (
                  <div className="mt-3 space-y-4 p-3.5 bg-slate-950/70 border border-slate-800 rounded-xl text-xs">
                    {/* Temperature Slider */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-300 flex items-center space-x-1">
                          <span>Độ biến thiên lấy mẫu (Sampling Randomness)</span>
                          <span title="Kiểm soát độ ngẫu nhiên phân phối xác suất token âm thanh; không cam kết biểu đạt cảm xúc cụ thể." className="text-slate-500 cursor-help">
                            <Info className="w-3 h-3 inline" />
                          </span>
                        </span>
                        <span className="font-mono text-emerald-400">{temperature.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min={0.1}
                        max={1.5}
                        step={0.05}
                        value={temperature}
                        onChange={(e) => {
                          setTemperature(parseFloat(e.target.value));
                          setActivePresetId('custom');
                        }}
                        className="w-full h-1.5 bg-slate-900 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                      />
                      <div className="flex justify-between text-[10px] text-slate-500">
                        <span>0.1 (Ổn định)</span>
                        <span>0.8 (Chuẩn)</span>
                        <span>1.5 (Đa dạng ngẫu nhiên)</span>
                      </div>
                    </div>

                    {/* Top-P Slider */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-300 flex items-center space-x-1">
                          <span>Ngưỡng Top-P (Nucleus Sampling)</span>
                          <span title="Chỉ chọn lọc từ nhóm token có tổng xác suất tích lũy đạt ngưỡng P." className="text-slate-500 cursor-help">
                            <Info className="w-3 h-3 inline" />
                          </span>
                        </span>
                        <span className="font-mono text-emerald-400">{topP.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min={0.1}
                        max={1.0}
                        step={0.01}
                        value={topP}
                        onChange={(e) => {
                          setTopP(parseFloat(e.target.value));
                          setActivePresetId('custom');
                        }}
                        className="w-full h-1.5 bg-slate-900 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                      />
                    </div>

                    {/* Top-K Slider */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-300 flex items-center space-x-1">
                          <span>Giới hạn Top-K</span>
                          <span title="Số lượng âm vị ứng viên có xác suất cao nhất tại mỗi bước sinh âm." className="text-slate-500 cursor-help">
                            <Info className="w-3 h-3 inline" />
                          </span>
                        </span>
                        <span className="font-mono text-emerald-400">{topK}</span>
                      </div>
                      <input
                        type="range"
                        min={1}
                        max={100}
                        step={1}
                        value={topK}
                        onChange={(e) => {
                          setTopK(parseInt(e.target.value, 10));
                          setActivePresetId('custom');
                        }}
                        className="w-full h-1.5 bg-slate-900 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                      />
                    </div>

                    {/* Repetition Penalty Slider */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-300 flex items-center space-x-1">
                          <span>Chống vấp / Lặp âm (Repetition Penalty)</span>
                          <span title="Hình phạt lặp lại âm tiết, giúp câu nói trôi chảy và hạn chế nói vấp." className="text-slate-500 cursor-help">
                            <Info className="w-3 h-3 inline" />
                          </span>
                        </span>
                        <span className="font-mono text-emerald-400">{repetitionPenalty.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min={1.0}
                        max={2.5}
                        step={0.05}
                        value={repetitionPenalty}
                        onChange={(e) => {
                          setRepetitionPenalty(parseFloat(e.target.value));
                          setActivePresetId('custom');
                        }}
                        className="w-full h-1.5 bg-slate-900 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                      />
                    </div>

                    {/* Reset Button */}
                    <button
                      type="button"
                      onClick={resetToDefaults}
                      className="w-full py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800 text-[11px] font-medium flex items-center justify-center space-x-1.5 transition-colors"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>Khôi phục giá trị mặc định</span>
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
