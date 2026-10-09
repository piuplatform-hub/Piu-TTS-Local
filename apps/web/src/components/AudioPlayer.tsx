import React, { useRef, useState, useEffect } from 'react';
import { Play, Pause, Download, Volume2, VolumeX, RotateCcw } from 'lucide-react';
import { api } from '../api/client';
import { ArtifactMetadata } from '../types';

interface AudioPlayerProps {
  artifactId: string;
}

export const AudioPlayer: React.FC<AudioPlayerProps> = ({ artifactId }) => {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [metadata, setMetadata] = useState<ArtifactMetadata | null>(null);

  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  useEffect(() => {
    // Fetch artifact metadata
    api.getArtifactMetadata(artifactId)
      .then((meta) => {
        setMetadata(meta);
        if (meta.duration_seconds > 0) {
          setDuration(meta.duration_seconds);
        }
      })
      .catch((err) => console.error('Failed to load artifact metadata', err));

    let active = true;
    api.fetchArtifactAudioBlob(artifactId)
      .then((url) => {
        if (active) setBlobUrl(url);
      })
      .catch((err) => console.error('Failed to load artifact audio blob', err));

    setIsPlaying(false);
    setCurrentTime(0);

    return () => {
      active = false;
    };
  }, [artifactId]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  const onTimeUpdate = () => {
    if (!audioRef.current) return;
    setCurrentTime(audioRef.current.currentTime);
    if (!duration && audioRef.current.duration) {
      setDuration(audioRef.current.duration);
    }
  };

  const onEnded = () => {
    setIsPlaying(false);
    setCurrentTime(0);
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = val;
      setCurrentTime(val);
    }
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setVolume(val);
    if (audioRef.current) {
      audioRef.current.volume = val;
      setIsMuted(val === 0);
    }
  };

  const toggleMute = () => {
    if (!audioRef.current) return;
    if (isMuted) {
      audioRef.current.volume = volume || 0.8;
      setIsMuted(false);
    } else {
      audioRef.current.volume = 0;
      setIsMuted(true);
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl">
      <audio
        ref={audioRef}
        src={blobUrl || undefined}
        onTimeUpdate={onTimeUpdate}
        onEnded={onEnded}
        onLoadedMetadata={() => {
          if (audioRef.current) {
            setDuration(audioRef.current.duration || 0);
          }
        }}
      />

      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Main Controls: Play/Pause, Replay */}
        <div className="flex items-center space-x-3 w-full sm:w-auto">
          <button
            onClick={togglePlay}
            className="w-12 h-12 rounded-full bg-emerald-500 hover:bg-emerald-400 active:bg-emerald-600 text-slate-950 flex items-center justify-center shadow-lg shadow-emerald-500/20 transition-all flex-shrink-0"
          >
            {isPlaying ? (
              <Pause className="w-5 h-5 fill-current" />
            ) : (
              <Play className="w-5 h-5 fill-current ml-0.5" />
            )}
          </button>

          <button
            onClick={() => {
              if (audioRef.current) {
                audioRef.current.currentTime = 0;
                setCurrentTime(0);
              }
            }}
            title="Phát lại từ đầu"
            className="p-2.5 rounded-xl bg-slate-800/60 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700/60 transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          {/* Time scrubber */}
          <div className="flex-1 sm:w-64 flex items-center space-x-3 px-2">
            <span className="text-xs font-mono text-slate-400 w-9 text-right">
              {formatTime(currentTime)}
            </span>
            <input
              type="range"
              min={0}
              max={duration || 1}
              step={0.01}
              value={currentTime}
              onChange={handleSeek}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-500"
            />
            <span className="text-xs font-mono text-slate-400 w-9">
              {formatTime(duration)}
            </span>
          </div>
        </div>

        {/* Volume & Download */}
        <div className="flex items-center space-x-4 w-full sm:w-auto justify-end">
          <div className="flex items-center space-x-2">
            <button
              onClick={toggleMute}
              className="p-1.5 text-slate-400 hover:text-slate-200 transition-colors"
            >
              {isMuted || volume === 0 ? (
                <VolumeX className="w-4 h-4" />
              ) : (
                <Volume2 className="w-4 h-4" />
              )}
            </button>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={isMuted ? 0 : volume}
              onChange={handleVolumeChange}
              className="w-20 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-500"
            />
          </div>

          <button
            onClick={() => api.downloadArtifactAudio(artifactId)}
            className="flex items-center space-x-1.5 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700/80 text-emerald-400 hover:text-emerald-300 border border-slate-700 text-xs font-medium transition-all shadow-sm"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Tải WAV</span>
          </button>
        </div>
      </div>

      {/* Artifact Metadata Pill */}
      {metadata && (
        <div className="mt-4 pt-3 border-t border-slate-800/80 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-400 font-mono">
          <span>Format: <strong className="text-slate-300 uppercase">{metadata.format}</strong></span>
          <span>Sample Rate: <strong className="text-slate-300">{metadata.sample_rate / 1000} kHz</strong></span>
          <span>Kích thước: <strong className="text-slate-300">{(metadata.file_size_bytes / 1024).toFixed(1)} KB</strong></span>
          <span>Thời lượng: <strong className="text-slate-300">{metadata.duration_seconds.toFixed(2)}s</strong></span>
        </div>
      )}
    </div>
  );
};
