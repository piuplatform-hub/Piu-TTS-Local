import {
  AuthStatus,
  AuthResponse,
  UserProfile,
  EngineInfo,
  JobRecord,
  ArtifactMetadata,
  ApiProblemError,
  Character,
  ScriptSegment,
  ProjectSummary,
  ProjectDetail,
  ProjectExport,
  TextSegmentationResult,
} from '../types';

const TOKEN_KEY = 'ai_voice_studio_token';

export class ApiError extends Error {
  problem: ApiProblemError;

  constructor(problem: ApiProblemError) {
    super(problem.detail || problem.title || 'An API error occurred');
    this.name = 'ApiError';
    this.problem = problem;
  }
}

class ApiClient {
  private token: string | null = null;

  constructor() {
    this.token = localStorage.getItem(TOKEN_KEY);
  }

  getToken(): string | null {
    return this.token;
  }

  setToken(token: string) {
    this.token = token;
    localStorage.setItem(TOKEN_KEY, token);
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem(TOKEN_KEY);
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(endpoint, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let problem: ApiProblemError;
      try {
        problem = await response.json();
      } catch {
        problem = {
          title: response.statusText,
          status: response.status,
          detail: 'Non-JSON error response from server.',
          code: `HTTP_${response.status}`,
        };
      }
      throw new ApiError(problem);
    }

    return response.json() as Promise<T>;
  }

  async getAuthStatus(): Promise<AuthStatus> {
    return this.request<AuthStatus>('/api/v1/auth/status');
  }

  async bootstrap(username: string, password: string, setupToken: string): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>('/api/v1/auth/bootstrap', {
      method: 'POST',
      body: JSON.stringify({
        username,
        password,
        setup_token: setupToken,
      }),
    });
    this.setToken(res.access_token);
    return res;
  }

  async login(username: string, password: string): Promise<AuthResponse> {
    const res = await this.request<AuthResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    this.setToken(res.access_token);
    return res;
  }

  async getMe(): Promise<UserProfile> {
    return this.request<UserProfile>('/api/v1/auth/me');
  }

  async getEngines(): Promise<EngineInfo[]> {
    return this.request<EngineInfo[]>('/api/v1/engines');
  }

  async submitTTSJob(params: {
    text: string;
    engine_id: string;
    language: string;
    voice_id?: string;
    speed?: number;
    idempotency_key?: string;
    priority?: number;
    parameters?: Record<string, any>;
  }): Promise<JobRecord> {
    return this.request<JobRecord>('/api/v1/jobs/speech', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async getJob(jobId: string): Promise<JobRecord> {
    return this.request<JobRecord>(`/api/v1/jobs/${jobId}`);
  }

  async listJobs(limit = 20, offset = 0): Promise<JobRecord[]> {
    return this.request<JobRecord[]>(`/api/v1/jobs?limit=${limit}&offset=${offset}`);
  }

  async cancelJob(jobId: string): Promise<JobRecord> {
    return this.request<JobRecord>(`/api/v1/jobs/${jobId}/cancel`, {
      method: 'POST',
    });
  }

  async retryJob(jobId: string): Promise<JobRecord> {
    return this.request<JobRecord>(`/api/v1/jobs/${jobId}/retry`, {
      method: 'POST',
    });
  }

  async getArtifactMetadata(artifactId: string): Promise<ArtifactMetadata> {
    return this.request<ArtifactMetadata>(`/api/v1/artifacts/${artifactId}`);
  }

  getArtifactAudioUrl(artifactId: string): string {
    return `/api/v1/artifacts/${artifactId}/file`;
  }

  async uploadReferenceAudio(file: File, voiceUseConsent: boolean): Promise<{ asset_id: string; message: string; asset: any }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('voice_use_consent', String(voiceUseConsent));

    const headers: Record<string, string> = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const res = await fetch('/api/v1/assets/reference-audio', {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!res.ok) {
      let problem: ApiProblemError;
      try {
        problem = await res.json();
      } catch {
        problem = {
          title: res.statusText,
          status: res.status,
          detail: 'Failed to upload reference audio.',
          code: `HTTP_${res.status}`,
        };
      }
      throw new ApiError(problem);
    }

    return res.json();
  }

  async listReferenceAudios(): Promise<any[]> {
    return this.request<any[]>('/api/v1/assets/reference-audio');
  }

  /**
   * Connects to Server-Sent Events (SSE) stream using Fetch API and ReadableStream
   * with standard 'Authorization: Bearer <token>' header. Tokens are NEVER placed in URLs (CWE-598).
   * Supports Last-Event-ID replay, automatic reconnect on drop, and polling fallback.
   */
  connectJobEvents(
    jobId: string,
    onEvent: (event: any) => void,
    onError?: (error: any) => void,
    initialLastEventId?: number
  ): () => void {
    let closed = false;
    let abortController: AbortController | null = null;
    let pollInterval: number | null = null;
    let currentLastEventId = initialLastEventId;
    let reconnectTimeout: number | null = null;

    const startPollingFallback = () => {
      if (closed || pollInterval !== null) return;
      pollInterval = window.setInterval(async () => {
        if (closed) return;
        try {
          const current = await this.getJob(jobId);
          onEvent({
            event_type: 'status_change',
            data: current,
          });
          if (['completed', 'failed', 'cancelled'].includes(current.status)) {
            if (pollInterval) clearInterval(pollInterval);
          }
        } catch (e) {
          if (onError) onError(e);
        }
      }, 1000);
    };

    const startFetchStream = async () => {
      if (closed) return;
      abortController = new AbortController();

      const headers: Record<string, string> = {
        'Accept': 'text/event-stream',
      };
      if (this.token) {
        headers['Authorization'] = `Bearer ${this.token}`;
      }
      if (currentLastEventId !== undefined && currentLastEventId !== null) {
        headers['Last-Event-ID'] = currentLastEventId.toString();
      }

      try {
        const url = `/api/v1/jobs/${jobId}/events${currentLastEventId ? `?last_event_id=${currentLastEventId}` : ''}`;
        const response = await fetch(url, {
          method: 'GET',
          headers,
          signal: abortController.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`SSE fetch failed with status ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (!closed) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const blocks = buffer.split('\n\n');
          // Retain any incomplete trailing chunk in buffer
          buffer = blocks.pop() || '';

          for (const block of blocks) {
            if (!block.trim()) continue;
            let eventType = 'message';
            let eventData = '';
            let eventId: number | undefined;

            for (const line of block.split('\n')) {
              if (line.startsWith('event:')) {
                eventType = line.slice(6).trim();
              } else if (line.startsWith('data:')) {
                eventData = line.slice(5).trim();
              } else if (line.startsWith('id:')) {
                const idVal = line.slice(3).trim();
                if (idVal) {
                  eventId = parseInt(idVal, 10);
                  currentLastEventId = eventId;
                }
              }
            }

            if (eventData) {
              try {
                const parsed = JSON.parse(eventData);
                onEvent({
                  id: eventId,
                  event_type: eventType,
                  data: parsed,
                });
                if (['completed', 'failed', 'cancelled'].includes(eventType)) {
                  closed = true;
                  return;
                }
              } catch (err) {
                console.error('Failed to parse SSE JSON payload', err);
              }
            }
          }
        }
      } catch (err: any) {
        if (closed || err?.name === 'AbortError') return;
        console.warn('Fetch SSE stream interrupted, reconnecting or falling back', err);
        if (onError) onError(err);

        if (!closed) {
          reconnectTimeout = window.setTimeout(() => {
            if (!closed) {
              startFetchStream().catch(() => startPollingFallback());
            }
          }, 1500);
        }
      }
    };

    startFetchStream();

    return () => {
      closed = true;
      if (abortController) {
        abortController.abort();
        abortController = null;
      }
      if (reconnectTimeout !== null) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
      }
      if (pollInterval !== null) {
        clearInterval(pollInterval);
        pollInterval = null;
      }
    };
  }

  // -------------------------------------------------------------
  // PHASE 4 STUDIO WORKSPACE METHODS
  // -------------------------------------------------------------
  async listProjects(): Promise<ProjectSummary[]> {
    return this.request<ProjectSummary[]>('/api/v1/projects');
  }

  async createProject(params: {
    title: string;
    description?: string;
    project_type?: 'narration' | 'dialogue';
    settings?: Record<string, any>;
  }): Promise<ProjectDetail> {
    return this.request<ProjectDetail>('/api/v1/projects', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async getProject(projectId: string): Promise<ProjectDetail> {
    return this.request<ProjectDetail>(`/api/v1/projects/${projectId}`);
  }

  async updateProject(
    projectId: string,
    params: {
      title?: string;
      description?: string;
      settings?: Record<string, any>;
      expected_version?: number;
    }
  ): Promise<ProjectDetail> {
    return this.request<ProjectDetail>(`/api/v1/projects/${projectId}`, {
      method: 'PATCH',
      body: JSON.stringify(params),
    });
  }

  async deleteProject(projectId: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/api/v1/projects/${projectId}`, {
      method: 'DELETE',
    });
  }

  // Character management
  async createCharacter(
    projectId: string,
    params: {
      name: string;
      description?: string;
      avatar_color?: string;
      engine_id: string;
      voice_id: string;
      parameters?: Record<string, any>;
      expected_project_version?: number;
    }
  ): Promise<Character> {
    return this.request<Character>(`/api/v1/projects/${projectId}/characters`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async updateCharacter(
    projectId: string,
    characterId: string,
    params: {
      name?: string;
      description?: string;
      avatar_color?: string;
      engine_id?: string;
      voice_id?: string;
      parameters?: Record<string, any>;
      expected_project_version?: number;
    }
  ): Promise<Character> {
    return this.request<Character>(`/api/v1/projects/${projectId}/characters/${characterId}`, {
      method: 'PATCH',
      body: JSON.stringify(params),
    });
  }

  async deleteCharacter(
    projectId: string,
    characterId: string,
    expectedProjectVersion?: number
  ): Promise<{ message: string }> {
    const url = expectedProjectVersion !== undefined
      ? `/api/v1/projects/${projectId}/characters/${characterId}?expected_project_version=${expectedProjectVersion}`
      : `/api/v1/projects/${projectId}/characters/${characterId}`;
    return this.request<{ message: string }>(url, {
      method: 'DELETE',
    });
  }

  // Segment management
  async addSegment(
    projectId: string,
    params: {
      sequence_order?: number;
      character_id?: string | null;
      text: string;
      language?: string;
      engine_id?: string;
      voice_id?: string;
      parameters?: Record<string, any>;
      pause_after_ms?: number;
      expected_project_version?: number;
    }
  ): Promise<ScriptSegment> {
    return this.request<ScriptSegment>(`/api/v1/projects/${projectId}/segments`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async updateSegment(
    projectId: string,
    segmentId: string,
    params: {
      character_id?: string | null;
      sequence_order?: number;
      text?: string;
      language?: string;
      engine_id?: string;
      voice_id?: string;
      parameters?: Record<string, any>;
      pause_after_ms?: number;
      expected_segment_version?: number;
      expected_project_version?: number;
    }
  ): Promise<ScriptSegment> {
    return this.request<ScriptSegment>(`/api/v1/projects/${projectId}/segments/${segmentId}`, {
      method: 'PATCH',
      body: JSON.stringify(params),
    });
  }

  async deleteSegment(
    projectId: string,
    segmentId: string,
    expectedProjectVersion?: number
  ): Promise<{ message: string }> {
    const url = expectedProjectVersion !== undefined
      ? `/api/v1/projects/${projectId}/segments/${segmentId}?expected_project_version=${expectedProjectVersion}`
      : `/api/v1/projects/${projectId}/segments/${segmentId}`;
    return this.request<{ message: string }>(url, {
      method: 'DELETE',
    });
  }

  async bulkSyncSegments(
    projectId: string,
    params: {
      expected_project_version: number;
      segments: Array<{
        id?: string;
        sequence_order: number;
        character_id?: string | null;
        text: string;
        language: string;
        engine_id: string;
        voice_id: string;
        parameters?: Record<string, any>;
        pause_after_ms?: number;
      }>;
    }
  ): Promise<ProjectDetail> {
    return this.request<ProjectDetail>(`/api/v1/projects/${projectId}/segments/sync`, {
      method: 'PUT',
      body: JSON.stringify(params),
    });
  }

  // Text Segmentation
  async previewTextSegmentation(params: {
    text: string;
    language?: 'vi' | 'zh' | 'en';
    max_chars_per_segment?: number;
  }): Promise<TextSegmentationResult> {
    return this.request<TextSegmentationResult>('/api/v1/projects/segment-text', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async autoSegmentProject(
    projectId: string,
    params: {
      text: string;
      language?: 'vi' | 'zh' | 'en';
      max_chars_per_segment?: number;
      default_engine_id?: string;
      default_voice_id?: string;
      expected_project_version?: number;
    }
  ): Promise<ScriptSegment[]> {
    return this.request<ScriptSegment[]>(`/api/v1/projects/${projectId}/auto-segment`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  // Rendering & Reconcile
  async renderSegment(projectId: string, segmentId: string): Promise<ScriptSegment> {
    return this.request<ScriptSegment>(`/api/v1/projects/${projectId}/segments/${segmentId}/render`, {
      method: 'POST',
    });
  }

  async renderBatch(
    projectId: string,
    params?: {
      segment_ids?: string[];
      only_stale_or_draft?: boolean;
    }
  ): Promise<ScriptSegment[]> {
    return this.request<ScriptSegment[]>(`/api/v1/projects/${projectId}/render-batch`, {
      method: 'POST',
      body: JSON.stringify(params || {}),
    });
  }

  async reconcileProject(projectId: string): Promise<ProjectDetail> {
    return this.request<ProjectDetail>(`/api/v1/projects/${projectId}/reconcile`, {
      method: 'POST',
    });
  }

  // Master Audio Export
  async exportMasterAudio(
    projectId: string,
    params: {
      format?: 'wav' | 'mp3';
      sample_rate?: number;
      normalize_loudness?: boolean;
      target_lufs?: number;
    }
  ): Promise<ProjectExport> {
    return this.request<ProjectExport>(`/api/v1/projects/${projectId}/export`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  async downloadMasterAudio(projectId: string, exportId: string, fallbackFilename?: string): Promise<void> {
    const url = `/api/v1/projects/${projectId}/exports/${exportId}/download`;
    const headers: Record<string, string> = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const res = await fetch(url, {
      method: 'GET',
      headers,
    });

    if (!res.ok) {
      let problem: ApiProblemError;
      try {
        problem = await res.json();
      } catch {
        problem = {
          title: res.statusText,
          status: res.status,
          detail: 'Failed to download master audio export.',
          code: `HTTP_${res.status}`,
        };
      }
      throw new ApiError(problem);
    }

    let filename = fallbackFilename || `master_export_${exportId.slice(0, 8)}.wav`;
    const disposition = res.headers.get('Content-Disposition');
    if (disposition) {
      const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
      if (match && match[1]) {
        filename = match[1].replace(/['"]/g, '').trim();
      }
    }

    const blob = await res.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => {
      window.URL.revokeObjectURL(blobUrl);
    }, 5000);
  }
}

export const api = new ApiClient();
