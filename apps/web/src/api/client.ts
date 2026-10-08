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

  async getArtifactMetadata(artifactId: string): Promise<ArtifactMetadata> {
    return this.request<ArtifactMetadata>(`/api/v1/artifacts/${artifactId}`);
  }

  getArtifactAudioUrl(artifactId: string): string {
    return `/api/v1/artifacts/${artifactId}/file`;
  }
}

export const api = new ApiClient();
