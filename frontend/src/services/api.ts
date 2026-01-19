import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor para adicionar token JWT automaticamente
api.interceptors.request.use((config) => {
  // Verifica tanto localStorage quanto sessionStorage
  const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Interceptor para tratar erros de autenticação
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token inválido ou expirado - limpa ambos storages
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_id');
      localStorage.removeItem('username');
      sessionStorage.removeItem('auth_token');
      sessionStorage.removeItem('user_id');
      sessionStorage.removeItem('username');
      // Não redireciona automaticamente - deixa o ProtectedRoute gerenciar
    }
    return Promise.reject(error);
  }
);

export interface VideoProcessRequest {
  youtube_url: string;
  source_language: string;
  target_language: string;
  gemini_api_key: string;
  force_retranslate?: boolean;
}

export interface VideoProcessResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'error';
  progress: number;
  message: string | null;
  video_id: string | null;
  error: string | null;
  translation_service: string | null;
}

export interface TranslationSegment {
  start: number;
  duration: number;
  original: string;
  translated: string;
}

export interface SubtitlesResponse {
  video_id: string;
  source_language: string;
  target_language: string;
  segments: TranslationSegment[];
}

export interface VideoCheckResponse {
  exists: boolean;
  translation_id: string | null;
  video_id: string | null;
}

export const videoApi = {
  process: async (data: VideoProcessRequest): Promise<VideoProcessResponse> => {
    const response = await api.post<VideoProcessResponse>('/api/video/process', data);
    return response.data;
  },

  check: async (
    youtube_url: string,
    source_language: string,
    target_language: string
  ): Promise<VideoCheckResponse> => {
    const response = await api.get<VideoCheckResponse>('/api/video/check', {
      params: { youtube_url, source_language, target_language },
    });
    return response.data;
  },

  getSubtitles: async (
    video_id: string,
    source_language: string,
    target_language: string
  ): Promise<SubtitlesResponse> => {
    const response = await api.get<SubtitlesResponse>(
      `/api/video/${video_id}/subtitles`,
      {
        params: { source_language, target_language },
      }
    );
    return response.data;
  },

  getJobStatus: async (job_id: string): Promise<JobStatusResponse> => {
    const response = await api.get<JobStatusResponse>(
      `/api/video/job/${job_id}/status`
    );
    return response.data;
  },

  listVideos: async (): Promise<{ videos: any[]; total: number }> => {
    const response = await api.get('/api/video/list');
    return response.data;
  },

  deleteTranslation: async (
    video_id: string,
    source_language: string,
    target_language: string
  ): Promise<{ message: string }> => {
    const response = await api.delete(`/api/video/${video_id}/translation`, {
      params: { source_language, target_language },
    });
    return response.data;
  },

  deleteVideo: async (
    video_id: string
  ): Promise<{ message: string; deleted_translations: number }> => {
    const response = await api.delete(`/api/video/${video_id}`);
    return response.data;
  },

  deleteAllVideos: async (): Promise<{ 
    message: string; 
    deleted_videos: number; 
    deleted_translations: number 
  }> => {
    const response = await api.delete('/api/video/all');
    return response.data;
  },

  getMusicPhrase: async (params: {
    direction: string;
    difficulty: string;
    video_ids?: string[];
  }): Promise<any> => {
    const response = await api.post('/api/practice/phrase/music-context', params);
    return response.data;
  },

  generatePracticePhrase: async (params: {
    direction: string;
    difficulty: string;
    video_ids?: string[];
    api_keys?: {
      openrouter?: string;
      groq?: string;
      together?: string;
    };
    custom_prompt?: string;
    preferred_agent?: { service: string; model: string };
  }): Promise<any> => {
    const response = await api.post('/api/practice/phrase/new-context', params);
    return response.data;
  },

  getAvailableAgents: async (apiKeys?: { gemini?: string; openrouter?: string; groq?: string; together?: string }): Promise<{ agents: Array<{ service: string; model: string; display_name: string; available: boolean }> }> => {
    const response = await api.post('/api/practice/available-agents', { api_keys: apiKeys || {} });
    return response.data;
  },

  checkPracticeAnswer: async (params: {
    phrase_id: string;
    user_answer: string;
    direction: string;
  }): Promise<{ is_correct: boolean; correct_answer: string; similarity: number }> => {
    const response = await api.post('/api/practice/check-answer', params);
    return response.data;
  },
};

export interface ApiKeyStatus {
  service: string;
  is_valid: boolean;
  models_status: Array<{
    name: string;
    available: boolean;
    blocked: boolean;
    status: string;
    category?: string; // text, reasoning, audio, video, code, multimodal
  }>;
  available_models: string[];
  blocked_models: string[];
  error: string | null;
  models_by_category?: {
    [category: string]: Array<{
      name: string;
      available: boolean;
      blocked: boolean;
      status: string;
      category?: string;
    }>;
  };
}

export interface ApiKeyResponse {
  id: string;
  service: string;
  created_at?: string;
  updated_at?: string;
}

export interface ApiKeyCreate {
  service: string;
  api_key: string;
}

export const apiKeysApi = {
  checkStatus: async (api_key: string, service: string = 'gemini'): Promise<ApiKeyStatus> => {
    const response = await api.post<ApiKeyStatus>('/api/keys/check-status', {
      api_key,
      service,
    });
    return response.data;
  },

  list: async (): Promise<{ api_keys: ApiKeyResponse[]; total: number }> => {
    const response = await api.get('/api/keys/list');
    return response.data;
  },

  create: async (keyData: ApiKeyCreate): Promise<ApiKeyResponse> => {
    const response = await api.post<ApiKeyResponse>('/api/keys/', keyData);
    return response.data;
  },

  delete: async (keyId: string): Promise<void> => {
    await api.delete(`/api/keys/${keyId}`);
  },

  deleteByService: async (service: string): Promise<void> => {
    await api.delete(`/api/keys/service/${service}`);
  },

  checkSavedStatus: async (service: string): Promise<ApiKeyStatus> => {
    const response = await api.post<ApiKeyStatus>(`/api/keys/${service}/check-status-saved`);
    return response.data;
  },
};

export interface UsageStats {
  service?: string;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  requests: number;
  models: Array<{
    model: string;
    tokens: number;
    input_tokens: number;
    output_tokens: number;
    requests: number;
  }>;
  daily_usage: Array<{
    date: string;
    total_tokens: number;
    requests: number;
  }>;
  period_days: number;
}

export interface UsageStatsResponse {
  services?: UsageStats[];
  service?: string;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  requests: number;
  models: Array<{
    model: string;
    tokens: number;
    input_tokens: number;
    output_tokens: number;
    requests: number;
  }>;
  daily_usage: Array<{
    date: string;
    total_tokens: number;
    requests: number;
  }>;
  period_days: number;
}

export const usageApi = {
  getStats: async (service?: string, days: number = 30): Promise<UsageStatsResponse> => {
    const params: any = { days };
    if (service) {
      params.service = service;
    }
    const response = await api.get<UsageStatsResponse>('/api/usage/stats', { params });
    return response.data;
  },
};

// ============================================
// AUTENTICAÇÃO
// ============================================

export interface RegisterRequest {
  email: string;
  username: string;
  native_language?: string;
  learning_language?: string;
}

export interface LoginRequest {
  email: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  username: string;
}

export interface UserProfile {
  id: string;
  email: string;
  username: string;
  native_language: string;
  learning_language: string;
  proficiency_level: string;
  total_chat_messages: number;
  total_practice_sessions: number;
  average_response_time: number;
  learning_context?: any;
  preferred_learning_style?: string;
  preferred_model?: string;
  created_at: string;
}

export const authApi = {
  register: async (data: RegisterRequest): Promise<TokenResponse> => {
    const response = await api.post<TokenResponse>('/api/auth/register', data);
    return response.data;
  },

  login: async (data: LoginRequest): Promise<TokenResponse> => {
    const response = await api.post<TokenResponse>('/api/auth/login', data);
    return response.data;
  },

  getProfile: async (): Promise<UserProfile> => {
    const response = await api.get<UserProfile>('/api/auth/me');
    return response.data;
  },
};

// ============================================
// CHAT
// ============================================

export interface ChatSessionCreate {
  mode: 'writing' | 'conversation';
  language: string;
  preferred_service?: string;
  preferred_model?: string;
}

export interface ChatSession {
  id: string;
  mode: string;
  language: string;
  model_service?: string;
  model_name?: string;
  is_active: boolean;
  message_count: number;
  session_context?: any;
  created_at: string;
  updated_at?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  content_type: 'text' | 'audio';
  audio_url?: string;
  transcription?: string;
  grammar_errors?: any;
  vocabulary_suggestions?: any;
  difficulty_score?: number;
  feedback_type?: string;
  created_at: string;
}

export interface ChatSessionWithMessages extends ChatSession {
  messages: ChatMessage[];
}

export interface ChatMessageCreate {
  content: string;
  content_type?: 'text' | 'audio';
  audio_url?: string;
  transcription?: string;
}

export interface AvailableModel {
  name: string;
  available: boolean;
  blocked?: boolean;
  category?: string;
}

export interface AvailableModelsResponse {
  gemini?: AvailableModel[];
  openrouter?: AvailableModel[];
  groq?: AvailableModel[];
  together?: AvailableModel[];
}

export interface ChangeModelRequest {
  service: string;
  model: string;
}

export const chatApi = {
  createSession: async (data: ChatSessionCreate): Promise<ChatSession> => {
    const response = await api.post<ChatSession>('/api/chat/sessions', data);
    return response.data;
  },

  listSessions: async (): Promise<ChatSession[]> => {
    const response = await api.get<ChatSession[]>('/api/chat/sessions');
    return response.data;
  },

  getSession: async (sessionId: string): Promise<ChatSessionWithMessages> => {
    const response = await api.get<ChatSessionWithMessages>(`/api/chat/sessions/${sessionId}`);
    return response.data;
  },

  sendMessage: async (sessionId: string, message: ChatMessageCreate): Promise<ChatMessage> => {
    const response = await api.post<ChatMessage>(`/api/chat/sessions/${sessionId}/messages`, message);
    return response.data;
  },

  sendAudio: async (sessionId: string, audioFile: File): Promise<ChatMessage> => {
    const formData = new FormData();
    formData.append('audio_file', audioFile);
    const response = await api.post<ChatMessage>(`/api/chat/sessions/${sessionId}/audio`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  closeSession: async (sessionId: string): Promise<void> => {
    await api.delete(`/api/chat/sessions/${sessionId}`);
  },

  getAvailableModels: async (): Promise<AvailableModelsResponse> => {
    const response = await api.get<AvailableModelsResponse>('/api/chat/available-models');
    return response.data;
  },

  changeModel: async (sessionId: string, modelData: ChangeModelRequest): Promise<ChatSession> => {
    const response = await api.patch<ChatSession>(`/api/chat/sessions/${sessionId}/model`, modelData);
    return response.data;
  },
};

export default api;
