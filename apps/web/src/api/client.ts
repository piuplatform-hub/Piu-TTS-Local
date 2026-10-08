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
}

export const api = new ApiClient();
