import React, { useState } from 'react';
import { X, Download, Sliders, AlertTriangle, CheckCircle, Music, RefreshCw, Volume2 } from 'lucide-react';
import { api, ApiError } from '../api/client';
import { ProjectDetail, ProjectExport } from '../types';

interface MasterExportModalProps {
  project: ProjectDetail;
  isOpen: boolean;
  onClose: () => void;
  onExportSuccess: (exp: ProjectExport) => void;
}

export const MasterExportModal: React.FC<MasterExportModalProps> = ({
  project,
  isOpen,
  onClose,
  onExportSuccess,
}) => {
  const [format, setFormat] = useState<'wav' | 'mp3'>('wav');
  const [sampleRate, setSampleRate] = useState<number>(48000);
  const [normalizeLoudness, setNormalizeLoudness] = useState<boolean>(true);
  const [targetLufs, setTargetLufs] = useState<number>(-16.0);
  const [exporting, setExporting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastExport, setLastExport] = useState<ProjectExport | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const handleDownload = async (exportId: string, exportFormat: string) => {
    try {
      setDownloadingId(exportId);
      const safeTitle = project.title.replace(/[^a-zA-Z0-9_\-]/g, '_');
      const filename = `${safeTitle}_${exportId.slice(0, 8)}.${exportFormat.toLowerCase()}`;
      await api.downloadMasterAudio(project.id, exportId, filename);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.problem.detail || err.message);
      } else {
        setError(err.message || 'Lỗi khi tải tệp âm thanh');
      }
    } finally {
      setDownloadingId(null);
    }
  };

  if (!isOpen) return null;

  const incompleteSegments = project.segments.filter(s => s.status !== 'completed');
  const canExport = project.segments.length > 0 && incompleteSegments.length === 0;

  const handleExport = async () => {
    setError(null);
    setExporting(true);
    try {
      const res = await api.exportMasterAudio(project.id, {
        format,
        sample_rate: sampleRate,
        normalize_loudness: normalizeLoudness,
        target_lufs: targetLufs,
      });
      setLastExport(res);
      onExportSuccess(res);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.problem.detail || err.message);
      } else {
        setError(err.message || 'Lỗi không xác định khi xuất bản âm thanh');
      }
    } finally {
      setExporting(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-slate-800 flex items-center justify-between sticky top-0 bg-slate-900/95 backdrop-blur z-10">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500/20 text-purple-400 border border-purple-500/30 flex items-center justify-center">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Xuất Bản Âm Thanh Master (DSP)</h2>
              <p className="text-xs text-slate-400">
                Ghép nối các đoạn âm thanh, chuẩn hóa tần số mẫu và cân bằng âm lượng EBU R128
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-2 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6">
          {/* Warning if incomplete segments exist */}
          {!canExport && (
            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs flex items-start space-x-3">
              <AlertTriangle className="w-5 h-5 shrink-0 text-amber-400" />
              <div>
                <p className="font-semibold mb-1">Dự án chưa sẵn sàng để xuất bản Master</p>
                {project.segments.length === 0 ? (
                  <p>Dự án hiện chưa có phân đoạn lời thoại nào. Vui lòng thêm phân đoạn trước.</p>
                ) : (
                  <p>
                    Còn {incompleteSegments.length} phân đoạn chưa hoàn thành hoặc cần tạo lại (stale/draft/rendering). 
                    Vui lòng bấm &quot;Tạo lại tất cả&quot; trước khi xuất file master hoàn chỉnh.
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Export Settings Form */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Định dạng âm thanh đầu ra
              </label>
              <select
                value={format}
                onChange={e => setFormat(e.target.value as 'wav' | 'mp3')}
                disabled={exporting}
                className="w-full bg-slate-800/80 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-purple-500"
              >
                <option value="wav">WAV (PCM 16-bit Lossless Studio Quality)</option>
                <option value="mp3">MP3 (320 kbps High Quality Audio)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Tần số lấy mẫu (Sample Rate)
              </label>
              <select
                value={sampleRate}
                onChange={e => setSampleRate(Number(e.target.value))}
                disabled={exporting}
                className="w-full bg-slate-800/80 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-purple-500"
              >
                <option value={48000}>48,000 Hz (Tiêu chuẩn VieNeu-TTS / Phim ảnh)</option>
                <option value={44100}>44,100 Hz (Tiêu chuẩn CD / Podcast thông dụng)</option>
                <option value={24000}>24,000 Hz (Tiêu chuẩn Qwen3-TTS gốc)</option>
              </select>
            </div>
          </div>

          {/* Loudness Normalization Settings */}
          <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/60 space-y-3">
            <div className="flex items-center justify-between">
              <label className="flex items-center space-x-2 text-xs font-semibold text-slate-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={normalizeLoudness}
                  onChange={e => setNormalizeLoudness(e.target.checked)}
                  disabled={exporting}
                  className="rounded border-slate-600 bg-slate-700 text-purple-600 focus:ring-purple-500 w-4 h-4"
                />
                <span className="flex items-center space-x-1.5">
                  <Volume2 className="w-4 h-4 text-purple-400" />
                  <span>Áp dụng chuẩn hóa âm lượng EBU R128 (Loudness Mastering)</span>
                </span>
              </label>
            </div>

            {normalizeLoudness && (
              <div className="pl-6 pt-2 border-t border-slate-700/40 grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Mục tiêu Integrated LUFS</label>
                  <select
                    value={targetLufs}
                    onChange={e => setTargetLufs(parseFloat(e.target.value))}
                    disabled={exporting}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
                  >
                    <option value={-16.0}>-16.0 LUFS (Podcast, YouTube, Sách nói trực tuyến)</option>
                    <option value={-23.0}>-23.0 LUFS (Tiêu chuẩn truyền hình EBU R128 / Broadcast)</option>
                    <option value={-14.0}>-14.0 LUFS (Spotify / Apple Music chuẩn lớn)</option>
                  </select>
                </div>
                <div className="flex items-center text-[11px] text-slate-400 leading-relaxed">
                  Tự động căn chỉnh mức áp suất âm thanh nhất quán giữa giọng đọc VieNeu và Qwen3, triệt tiêu chênh lệch âm lượng.
                </div>
              </div>
            )}
          </div>

          {/* Summary & Metrics */}
          <div className="p-4 rounded-xl bg-purple-950/20 border border-purple-500/20 flex items-center justify-between text-xs">
            <div className="space-y-1">
              <span className="text-slate-400 block">Tổng phân đoạn hợp nhất</span>
              <span className="text-white font-semibold">{project.segments.length} đoạn lời thoại</span>
            </div>
            <div className="space-y-1">
              <span className="text-slate-400 block">Thời lượng ước tính</span>
              <span className="text-purple-300 font-mono font-semibold">
                {project.segments.reduce((acc, s) => acc + (s.pause_after_ms / 1000), 0).toFixed(1)}s + thời gian đọc
              </span>
            </div>
            <div className="space-y-1">
              <span className="text-slate-400 block">Tiến trình sẵn sàng</span>
              <span className={`font-semibold ${canExport ? 'text-emerald-400' : 'text-amber-400'}`}>
                {project.segments.length > 0
                  ? `${Math.round(((project.segments.length - incompleteSegments.length) / project.segments.length) * 100)}%`
                  : '0%'}
              </span>
            </div>
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-300 text-xs">
              {error}
            </div>
          )}

          {/* Last Export Result Banner */}
          {lastExport && (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 space-y-3">
              <div className="flex items-center space-x-2 text-sm font-bold text-emerald-400">
                <CheckCircle className="w-5 h-5 text-emerald-400" />
                <span>Xuất bản Master thành công!</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono text-slate-300">
                <div>
                  <span className="text-slate-500 block text-[10px]">ĐỊNH DẠNG</span>
                  {lastExport.format.toUpperCase()} ({lastExport.sample_rate}Hz)
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">THỜI LƯỢNG</span>
                  {lastExport.duration_seconds.toFixed(2)}s
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">DUNG LƯỢNG</span>
                  {formatFileSize(lastExport.file_size_bytes)}
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">ÂM LƯỢNG LUFS</span>
                  {lastExport.loudness_lufs !== null && lastExport.loudness_lufs !== undefined
                    ? `${lastExport.loudness_lufs.toFixed(1)} LUFS`
                    : 'N/A'}
                </div>
              </div>
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => handleDownload(lastExport.id, lastExport.format)}
                  disabled={downloadingId === lastExport.id}
                  className="inline-flex items-center space-x-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-md transition-colors cursor-pointer"
                >
                  <Download className="w-4 h-4" />
                  <span>Tải File Âm Thanh Master Ngay ({lastExport.format.toUpperCase()})</span>
                </button>
              </div>
            </div>
          )}

          {/* Previous Exports History */}
          {project.exports && project.exports.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Lịch sử các bản Master trước đó ({project.exports.length})
              </h3>
              <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
                {project.exports.map(exp => (
                  <div
                    key={exp.id}
                    className="p-2.5 rounded-lg bg-slate-800/40 border border-slate-700/50 flex items-center justify-between text-xs"
                  >
                    <div className="flex items-center space-x-2">
                      <Music className="w-4 h-4 text-purple-400" />
                      <div>
                        <span className="font-semibold text-slate-200">
                          {exp.format.toUpperCase()} • {exp.sample_rate}Hz
                        </span>
                        <span className="text-slate-500 text-[10px] ml-2">
                          {new Date(exp.created_at).toLocaleString('vi-VN')}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center space-x-3">
                      <span className="text-slate-400 font-mono text-[11px]">
                        {exp.duration_seconds.toFixed(1)}s • {formatFileSize(exp.file_size_bytes)}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleDownload(exp.id, exp.format)}
                        disabled={downloadingId === exp.id}
                        className="p-1.5 rounded-md bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-slate-200 transition-colors cursor-pointer"
                        title="Tải về"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-800 bg-slate-900/90 flex items-center justify-end space-x-3 sticky bottom-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            Đóng
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={!canExport || exporting}
            className={`flex items-center space-x-2 px-5 py-2.5 rounded-lg text-xs font-bold transition-all shadow-lg ${
              canExport && !exporting
                ? 'bg-purple-600 hover:bg-purple-500 text-white shadow-purple-900/40'
                : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
            }`}
          >
            {exporting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin text-purple-300" />
                <span>Đang xử lý DSP & Ghép nối FFmpeg...</span>
              </>
            ) : (
              <>
                <Download className="w-4 h-4" />
                <span>Bắt Đầu Ghép Nối & Xuất Bản Master</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
