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
