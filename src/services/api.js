import axios from 'axios';

// Backend API base URL
const API_BASE_URL = 'http://127.0.0.1:8000';

// Axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API fonksiyonları
export const chatAPI = {
  // Mesaj gönder
  sendMessage: async (message, repositoryUrl = null, conversationId = null) => {
    const response = await api.post('/api/chat/send', {
      message,
      repository_url: repositoryUrl,
      conversation_id: conversationId,
    });
    return response.data;
  },

  // Sohbet geçmişini getir
  getConversation: async (conversationId) => {
    const response = await api.get(`/api/chat/conversations/${conversationId}`);
    return response.data;
  },

  // Sohbeti sil
  deleteConversation: async (conversationId) => {
    const response = await api.delete(`/api/chat/conversations/${conversationId}`);
    return response.data;
  },
};

export const repositoryAPI = {
  // Repository listesi
  listRepositories: async () => {
    const response = await api.get('/api/repository/');
    return response.data;
  },

  // Repository analiz et
  analyzeRepository: async (repositoryUrl) => {
    const response = await api.post('/api/repository/analyze', null, {
      params: { repository_url: repositoryUrl },
    });
    return response.data;
  },

  // Repository istatistikleri
  getRepositoryStats: async (repoName) => {
    const response = await api.get(`/api/repository/${repoName}/stats`);
    return response.data;
  },
};

export default api;