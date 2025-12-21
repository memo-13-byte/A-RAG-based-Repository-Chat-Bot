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

// ============================================================================
// CHAT API
// ============================================================================
export const chatAPI = {
  // Send message (Phase 2: Enhanced with RAG support, Phase3: add useGraph parameter)
  sendMessage: async (message, repositoryUrl = null, conversationId = null, useRAG = true, autoIndex = true, useGraph = true) => {
    const response = await api.post('/api/chat/send', {
      message,
      repository_url: repositoryUrl,
      conversation_id: conversationId,
      use_llm: true,
      use_rag: useRAG,
      auto_index: autoIndex,
      use_graph: useGraph,  // ← ADD THIS LINE
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

  // NEW: Index repository for RAG
  indexRepository: async (repositoryUrl, includeCode = true, maxFiles = 50) => {
    const response = await api.post('/api/chat/index', null, {
      params: {
        repository_url: repositoryUrl,
        include_code: includeCode,
        max_files: maxFiles,
      },
    });
    return response.data;
  },

  // NEW: Check index status
  getIndexStatus: async (repositoryUrl) => {
    const response = await api.get('/api/chat/index-status', {
      params: { repository_url: repositoryUrl },
    });
    return response.data;
  },

  // NEW: Delete index
  deleteIndex: async (repositoryUrl) => {
    const response = await api.delete('/api/chat/index', {
      params: { repository_url: repositoryUrl },
    });
    return response.data;
  },
};

// ============================================================================
// REPOSITORY API
// ============================================================================
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

  // Repository README
  getRepositoryReadme: async (repoName) => {
    const response = await api.get(`/api/repository/${repoName}/readme`);
    return response.data;
  },

  // NEW: Repository file tree (Phase 2 format - recommended)
  getRepositoryFiles: async (repoName, path = '') => {
    const response = await api.get('/api/repository/files', {
      params: {
        repo_name: repoName,
        path: path,
      },
    });
    return response.data;
  },

  // LEGACY: Phase 1 format (still works but deprecated)
  getRepositoryFilesLegacy: async (repoName, path = '') => {
    const response = await api.get(`/api/repository/${repoName}/files`, {
      params: { path },
    });
    return response.data;
  },

  // Delete repository
  deleteRepository: async (repoName) => {
    const response = await api.delete(`/api/repository/${repoName}`);
    return response.data;
  },
};

// ============================================================================
// RAG API (Phase 2 - NEW!)
// ============================================================================
export const ragAPI = {
  // Index repository for RAG
  indexRepository: async (repoUrl, includeReadme = true, includeCode = true, maxFiles = 50) => {
    const response = await api.post('/api/rag/index', {
      repo_url: repoUrl,
      include_readme: includeReadme,
      include_code_files: includeCode,
      max_files: maxFiles,
    });
    return response.data;
  },

  // Semantic code search
  searchCode: async (repoName, query, nResults = 5) => {
    const response = await api.post('/api/rag/search', {
      repo_name: repoName,
      query: query,
      n_results: nResults,
    });
    return response.data;
  },

  // Generate RAG-powered answer
  generateAnswer: async (repoName, question, nResults = 3) => {
    const response = await api.post('/api/rag/answer', {
      repo_name: repoName,
      question: question,
      n_results: nResults,
    });
    return response.data;
  },

  // List all indexed collections
  listCollections: async () => {
    const response = await api.get('/api/rag/collections');
    return response.data;
  },

  // Get collection info
  getCollectionInfo: async (collectionName) => {
    const response = await api.get(`/api/rag/collections/${collectionName}`);
    return response.data;
  },

  // Delete collection
  deleteCollection: async (collectionName) => {
    const response = await api.delete(`/api/rag/collections/${collectionName}`);
    return response.data;
  },

  // RAG health check
  healthCheck: async () => {
    const response = await api.get('/api/rag/health');
    return response.data;
  },
};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

// Check if RAG is available for a repository
export const isRAGAvailable = async (repositoryUrl) => {
  try {
    const status = await chatAPI.getIndexStatus(repositoryUrl);
    return status.indexed;
  } catch (error) {
    console.error('Error checking RAG status:', error);
    return false;
  }
};

// Auto-index repository if not indexed
export const ensureRepositoryIndexed = async (repositoryUrl) => {
  try {
    const status = await chatAPI.getIndexStatus(repositoryUrl);
    if (!status.indexed) {
      console.log('Repository not indexed, indexing now...');
      const result = await chatAPI.indexRepository(repositoryUrl);
      return result;
    }
    return { status: 'already_indexed', ...status };
  } catch (error) {
    console.error('Error ensuring repository indexed:', error);
    throw error;
  }
};

export default api;