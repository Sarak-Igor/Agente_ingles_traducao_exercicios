import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

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
  }>;
  available_models: string[];
  blocked_models: string[];
  error: string | null;
}

export const apiKeysApi = {
  checkStatus: async (api_key: string, service: string = 'gemini'): Promise<ApiKeyStatus> => {
    const response = await api.post<ApiKeyStatus>('/api/keys/check-status', {
      api_key,
      service,
    });
    return response.data;
  },

  list: async (): Promise<{ api_keys: any[]; total: number }> => {
    const response = await api.get('/api/keys/list');
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

export default api;
