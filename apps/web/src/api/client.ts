import {
  AuthStatus,
  AuthResponse,
  UserProfile,
  EngineInfo,
  JobRecord,
  ArtifactMetadata,
  ApiProblemError,
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

  /**
   * Connects to Server-Sent Events (SSE) stream for a job with automatic query token auth
   * and polling fallback. Returns a cleanup unsubscribe function.
   */
  connectJobEvents(
    jobId: string,
    onEvent: (event: any) => void,
    onError?: (error: any) => void,
    lastEventId?: number
  ): () => void {
    let closed = false;
    let eventSource: EventSource | null = null;
    let pollInterval: number | null = null;

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

    try {
      const token = this.getToken() || '';
      const queryParams = new URLSearchParams({ token });
      if (lastEventId !== undefined && lastEventId !== null) {
        queryParams.set('last_event_id', lastEventId.toString());
      }

      const sseUrl = `/api/v1/jobs/${jobId}/events?${queryParams.toString()}`;
      eventSource = new EventSource(sseUrl);

      const eventTypes = ['status_change', 'progress', 'heartbeat', 'completed', 'failed', 'cancelled'];
      eventTypes.forEach((type) => {
        eventSource!.addEventListener(type, (e: MessageEvent) => {
          if (closed) return;
          try {
            const data = JSON.parse(e.data);
            onEvent({
              id: e.lastEventId ? parseInt(e.lastEventId, 10) : undefined,
              event_type: type,
              data,
            });
            if (['completed', 'failed', 'cancelled'].includes(type)) {
              if (eventSource) eventSource.close();
            }
          } catch (err) {
            console.error('Failed to parse SSE payload', err);
          }
        });
      });

      eventSource.onerror = (e) => {
        if (closed) return;
        console.warn('SSE stream error, switching to polling fallback', e);
        if (onError) onError(e);
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
        startPollingFallback();
      };
    } catch (e) {
      console.warn('Failed to initialize EventSource, using polling fallback', e);
      startPollingFallback();
    }

    return () => {
      closed = true;
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      if (pollInterval !== null) {
        clearInterval(pollInterval);
        pollInterval = null;
      }
    };
  }
}

export const api = new ApiClient();
