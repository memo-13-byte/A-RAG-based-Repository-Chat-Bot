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

// API functions
export const chatAPI = {
  // Send message
  sendMessage: async (message, repositoryUrl = null, conversationId = null) => {
    const response = await api.post('/api/chat/send', {
      message,
      repository_url: repositoryUrl,
      conversation_id: conversationId,
    });
    return response.data;
  },

  // Get chat history
  getConversation: async (conversationId) => {
    const response = await api.get(`/api/chat/conversations/${conversationId}`);
    return response.data;
  },

  // Delete chat
  deleteConversation: async (conversationId) => {
    const response = await api.delete(`/api/chat/conversations/${conversationId}`);
    return response.data;
  },
};

export const repositoryAPI = {
  // Repository list
  listRepositories: async () => {
    const response = await api.get('/api/repository/');
    return response.data;
  },

  // Analyze repository
  analyzeRepository: async (repositoryUrl) => {
    const response = await api.post('/api/repository/analyze', null, {
      params: { repository_url: repositoryUrl },
    });
    return response.data;
  },

  // Repository statistics
  getRepositoryStats: async (repoName) => {
    const response = await api.get(`/api/repository/${repoName}/stats`);
    return response.data;
  },
};

export default api;