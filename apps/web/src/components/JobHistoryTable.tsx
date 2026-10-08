import React, { useState, useEffect } from 'react';
import { RefreshCw, Play, Download, Clock, CheckCircle2, AlertCircle, RotateCw } from 'lucide-react';
import { api } from '../api/client';
import { JobRecord } from '../types';
import { AudioPlayer } from './AudioPlayer';

export const JobHistoryTable: React.FC = () => {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeArtifactId, setActiveArtifactId] = useState<string | null>(null);

  const fetchJobs = () => {
    setLoading(true);
    api.listJobs(50, 0)
      .then((data) => setJobs(data))
      .catch((err) => console.error('Failed to fetch jobs', err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div className="flex items-center justify-between pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Lịch Sử Tạo Giọng Nói</h1>
          <p className="text-xs text-slate-400 mt-1">
            Danh sách các yêu cầu tổng hợp âm thanh đã xử lý trên máy cục bộ.
          </p>
        </div>
        <button
          onClick={fetchJobs}
          disabled={loading}
          className="flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-xs font-medium transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Làm mới</span>
        </button>
      </div>

      {/* Selected active audio player drawer */}
      {activeArtifactId && (
        <div className="p-4 bg-slate-900 border border-emerald-500/30 rounded-2xl shadow-xl space-y-2">
          <div className="flex items-center justify-between text-xs text-emerald-400 font-medium">
            <span>Đang phát Audio Artifact: {activeArtifactId}</span>
            <button
              onClick={() => setActiveArtifactId(null)}
              className="text-slate-400 hover:text-white text-xs"
            >
              Đóng
            </button>
          </div>
          <AudioPlayer artifactId={activeArtifactId} />
        </div>
      )}

      {/* Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/60 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-3.5 px-4 font-medium">Job ID</th>
                <th className="py-3.5 px-4 font-medium">Engine</th>
                <th className="py-3.5 px-4 font-medium">Trạng thái</th>
                <th className="py-3.5 px-4 font-medium">Tiến độ</th>
                <th className="py-3.5 px-4 font-medium">Thời gian</th>
                <th className="py-3.5 px-4 font-medium text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-500">
                    {loading ? 'Đang tải danh sách...' : 'Chưa có yêu cầu tổng hợp nào.'}
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3.5 px-4 font-mono text-slate-400">
                      {job.id.slice(0, 8)}...
                    </td>
                    <td className="py-3.5 px-4 font-medium text-white">
                      {job.engine_id}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border capitalize bg-slate-950 border-slate-800">
                        {job.status === 'completed' && (
                          <>
                            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                            <span className="text-emerald-400">{job.status}</span>
                          </>
                        )}
                        {job.status === 'running' && (
                          <>
                            <RotateCw className="w-3 h-3 text-emerald-400 animate-spin" />
                            <span className="text-emerald-400">{job.status}</span>
                          </>
                        )}
                        {job.status === 'queued' && (
                          <>
                            <Clock className="w-3 h-3 text-amber-400" />
                            <span className="text-amber-400">{job.status}</span>
                          </>
                        )}
                        {job.status === 'failed' && (
                          <>
                            <AlertCircle className="w-3 h-3 text-red-400" />
                            <span className="text-red-400">{job.status}</span>
                          </>
                        )}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono">
                      {job.progress_percent}%
                    </td>
                    <td className="py-3.5 px-4 text-slate-400">
                      {new Date(job.queued_at).toLocaleTimeString('vi-VN')}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      {job.artifact_id && (
                        <div className="flex items-center justify-end space-x-2">
                          <button
                            onClick={() => setActiveArtifactId(job.artifact_id!)}
                            className="p-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 transition-colors"
                            title="Nghe audio"
                          >
                            <Play className="w-3.5 h-3.5" />
                          </button>
                          <a
                            href={api.getArtifactAudioUrl(job.artifact_id)}
                            download={`speech-${job.artifact_id.slice(0, 8)}.wav`}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                            title="Tải về"
                          >
                            <Download className="w-3.5 h-3.5" />
                          </a>
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
