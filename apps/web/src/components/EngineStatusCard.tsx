import React, { useState, useEffect } from 'react';
import { Cpu, ShieldCheck, HeartPulse, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import { EngineInfo } from '../types';

export const EngineStatusCard: React.FC = () => {
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchEngines = () => {
    setLoading(true);
    api.getEngines()
      .then((data) => setEngines(data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchEngines();
  }, []);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div className="flex items-center justify-between pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">AI Engine Registry</h1>
          <p className="text-xs text-slate-400 mt-1">
            Các engine nội suy được quản lý và bảo vệ trong các tiến trình con riêng biệt.
          </p>
        </div>
        <button
          onClick={fetchEngines}
          disabled={loading}
          className="flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-xs font-medium transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Làm mới</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {engines.map((eng) => (
          <div
            key={eng.id}
            className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5 relative overflow-hidden"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                  <Cpu className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">{eng.name}</h3>
                  <p className="text-xs text-slate-400 font-mono">ID: {eng.id} (v{eng.version})</p>
                </div>
              </div>

              <span className="flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span className="capitalize">{eng.approval_status}</span>
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 pt-2 text-xs">
              <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80">
                <span className="text-slate-500 block text-[11px]">Thiết bị thực thi</span>
                <span className="font-semibold text-slate-200 uppercase">{eng.device_target}</span>
              </div>
              <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800/80">
                <span className="text-slate-500 block text-[11px]">Preset Voices</span>
                <span className="font-semibold text-slate-200">{eng.preset_voices.length} giọng sẵn sàng</span>
              </div>
            </div>

            <div className="space-y-2">
              <span className="text-[11px] text-slate-400 font-medium">Năng lực (Capabilities):</span>
              <div className="flex flex-wrap gap-1.5">
                {eng.capabilities.map((c) => (
                  <span
                    key={c}
                    className="px-2 py-0.5 rounded-lg bg-slate-800 text-slate-300 text-[10px] font-mono border border-slate-700/60"
                  >
                    {c}
                  </span>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <span className="text-[11px] text-slate-400 font-medium">Ngôn ngữ hỗ trợ:</span>
              <div className="flex flex-wrap gap-1.5">
                {eng.supported_languages.map((l) => (
                  <span
                    key={l}
                    className="px-2 py-0.5 rounded-lg bg-emerald-950/40 text-emerald-300 text-[10px] font-medium border border-emerald-800/40"
                  >
                    {l === 'vi' ? 'Tiếng Việt (vi)' : l === 'zh' ? 'Tiếng Trung (zh)' : l === 'en' ? 'English (en)' : l}
                  </span>
                ))}
              </div>
            </div>

            <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
              <div className="flex items-center space-x-1.5 text-emerald-400">
                <HeartPulse className="w-3.5 h-3.5" />
                <span>Tiến trình Worker: Running</span>
              </div>
              <span className="font-mono text-[11px]">Port: Loopback</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
