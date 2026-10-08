export interface UserProfile {
  id: string;
  username: string;
  role: string;
  created_at: string;
}

export interface AuthStatus {
  needs_onboarding: boolean;
  total_users: number;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

export interface PresetVoice {
  id: string;
  name: string;
  language: string;
  gender: string;
}

export interface EngineInfo {
  id: string;
  name: string;
  version: string;
  approval_status: string;
  device_target: string;
  capabilities: string[];
  supported_languages: string[];
  preset_voices: PresetVoice[];
  parameters_schema: Record<string, any>;
}

export type JobStatusType = 'queued' | 'preparing' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface JobRecord {
  id: string;
  user_id: string;
  engine_id: string;
  job_type: string;
  status: JobStatusType;
  progress_percent: number;
  priority?: number;
  resource_type?: string;
  attempt_count?: number;
  max_retries?: number;
  waiting_reason?: string | null;
  artifact_id?: string | null;
  error_details?: {
    code?: string;
    message?: string;
    attempt_count?: number;
  } | null;
  queued_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface ArtifactMetadata {
  id: string;
  owner_id: string;
  file_size_bytes: number;
  duration_seconds: number;
  sample_rate: number;
  format: string;
  created_at: string;
}

export interface ApiProblemError {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  code?: string;
  instance?: string;
}

// -------------------------------------------------------------
// PHASE 4 STUDIO WORKSPACE & MASTERING TYPES
// -------------------------------------------------------------
export interface Character {
  id: string;
  project_id: string;
  name: string;
  description?: string | null;
  avatar_color: string;
  engine_id: string;
  voice_id: string;
  parameters: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface SegmentRevision {
  id: string;
  segment_id: string;
  revision_number: number;
  text: string;
  artifact_id: string;
  duration_seconds: number;
  sample_rate: number;
  format: string;
  created_at: string;
}

export type SegmentStatusType = 'draft' | 'queued' | 'rendering' | 'completed' | 'failed' | 'stale';

export interface ScriptSegment {
  id: string;
  project_id: string;
  character_id?: string | null;
  sequence_order: number;
  text: string;
  language: string;
  engine_id: string;
  voice_id: string;
  parameters: Record<string, any>;
  pause_after_ms: number;
  status: SegmentStatusType;
  active_artifact_id?: string | null;
  last_job_id?: string | null;
  text_hash: string;
  version: number;
  revisions: SegmentRevision[];
  created_at: string;
  updated_at: string;
}

export interface ProjectExport {
  id: string;
  project_id: string;
  user_id: string;
  format: 'wav' | 'mp3';
  sample_rate: number;
  file_path: string;
  file_size_bytes: number;
  duration_seconds: number;
  sha256_checksum: string;
  loudness_lufs?: number | null;
  segment_count: number;
  created_at: string;
}

export interface ProjectSummary {
  id: string;
  user_id: string;
  title: string;
  description?: string | null;
  project_type: 'narration' | 'dialogue';
  settings: Record<string, any>;
  version: number;
  segment_count: number;
  completed_segment_count: number;
  total_audio_duration_s: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail {
  id: string;
  user_id: string;
  title: string;
  description?: string | null;
  project_type: 'narration' | 'dialogue';
  settings: Record<string, any>;
  version: number;
  characters: Character[];
  segments: ScriptSegment[];
  exports: ProjectExport[];
  created_at: string;
  updated_at: string;
}

export interface TextSegmentItem {
  index: number;
  text: string;
  char_count: number;
}

export interface TextSegmentationResult {
  language: string;
  total_chars: number;
  segment_count: number;
  segments: TextSegmentItem[];
}

