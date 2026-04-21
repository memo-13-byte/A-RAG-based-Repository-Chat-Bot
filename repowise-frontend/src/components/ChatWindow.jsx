import React, { useState, useEffect, useRef } from 'react';
import { chatAPI, repositoryAPI, ragAPI, isRAGAvailable } from '../services/api';

/**
 * 🌊 STREAMING-ENHANCED Chat Window Component
 *
 * New Features:
 * - Real-time streaming responses (typewriter effect)
 * - Streaming toggle (stream vs normal mode)
 * - Progressive message rendering
 * - Abort streaming capability
 * - All existing features preserved
 */
const EnhancedChatWindow = ({ selectedRepository }) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [conversationId, setConversationId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [ragEnabled, setRagEnabled] = useState(true);
  const [autoIndex, setAutoIndex] = useState(true);
  const [indexStatus, setIndexStatus] = useState(null);
  const [isIndexing, setIsIndexing] = useState(false);

  // Search Mode State
  const [searchMode, setSearchMode] = useState('auto');
  const [showAdvanced, setShowAdvanced] = useState(false);

  // 🆕 STREAMING STATE
  const [streamingEnabled, setStreamingEnabled] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState('');
  const abortControllerRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessage]);

  // Check RAG status when repository changes
  useEffect(() => {
    if (selectedRepository) {
      checkIndexStatus();
    }
  }, [selectedRepository]);

  // Check if repository is indexed
  const checkIndexStatus = async () => {
    if (!selectedRepository) return;
    try {
        const status = await chatAPI.getIndexStatus(selectedRepository.url);
        setIndexStatus(status);
    } catch (error) {
        console.error('Error checking index status:', error);
        setIndexStatus(null);
    }
  };

  // Manually index repository
  const handleManualIndex = async () => {
    if (!selectedRepository || isIndexing) return;
    setIsIndexing(true);
    try {
      const result = await chatAPI.indexRepository(selectedRepository.url, true, 50);
      console.log('Indexing result:', result);
      await checkIndexStatus();
      alert(`Successfully indexed! ${result.document_count || 0} chunks created.`);
    } catch (error) {
      console.error('Error indexing repository:', error);
      alert('Failed to index repository. Check console for details.');
    } finally {
      setIsIndexing(false);
    }
  };

  // 🆕 STREAMING: Send message with streaming support
  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    setLoading(true);

    // Add user message to chat
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: userMessage, timestamp: new Date().toISOString() },
    ]);

    try {
      const useGraph = searchMode !== 'vector';

      // 🌊 STREAMING MODE
      if (streamingEnabled) {
        await handleStreamingResponse(userMessage, useGraph);
      }
      // 📄 NORMAL MODE
      else {
        await handleNormalResponse(userMessage, useGraph);
      }

    } catch (error) {
      console.error('Error sending message:', error);
      setMessages((prev) => [
        ...prev,
        {
          role: 'error',
          content: 'Failed to get response. Please try again.',
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
      setIsStreaming(false);
      setStreamingMessage('');
    }
  };

  // 🆕 Handle streaming response
  const handleStreamingResponse = async (userMessage, useGraph) => {
    setIsStreaming(true);
    setStreamingMessage('');

    // Create abort controller
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch('/api/chat/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
          repository_url: selectedRepository.url,
          conversation_id: conversationId,
          use_llm: true,
          use_rag: ragEnabled,
          auto_index: autoIndex,
          use_graph: useGraph,
          stream: true,  // ← ENABLE STREAMING!
        }),
        signal: abortControllerRef.current.signal,
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let fullMessage = '';
      let metadata = {};

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'start') {
                // Save conversation ID
                if (!conversationId) {
                  setConversationId(data.conversation_id);
                }
              }
              else if (data.type === 'sources') {
                // Save sources metadata
                metadata.sources = data.sources;
              }
              else if (data.type === 'chunk') {
                // Append chunk to streaming message
                fullMessage += data.content;
                setStreamingMessage(fullMessage);
              }
              else if (data.type === 'done') {
                // Stream completed - add full message to chat
                setMessages((prev) => [
                  ...prev,
                  {
                    role: 'assistant',
                    content: fullMessage,
                    sources: metadata.sources || [],
                    confidence: 0.9,  // Streaming mode assumed high confidence
                    rag_used: ragEnabled,
                    graph_used: useGraph,
                    timestamp: new Date().toISOString(),
                    streamed: true,
                  },
                ]);
                setStreamingMessage('');
              }
              else if (data.type === 'error') {
                throw new Error(data.message);
              }
            } catch (parseError) {
              console.error('Error parsing SSE data:', parseError);
            }
          }
        }
      }

    } catch (error) {
      if (error.name === 'AbortError') {
        console.log('Streaming aborted by user');
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: streamingMessage + '\n\n*[Response interrupted]*',
            timestamp: new Date().toISOString(),
            streamed: true,
            interrupted: true,
          },
        ]);
      } else {
        throw error;
      }
    }
  };

  // 📄 Handle normal (non-streaming) response
  const handleNormalResponse = async (userMessage, useGraph) => {
    const response = await chatAPI.sendMessage(
      userMessage,
      selectedRepository.url,
      conversationId,
      ragEnabled,
      autoIndex,
      useGraph
    );

    // Save conversation ID
    if (!conversationId) {
      setConversationId(response.conversation_id);
    }

    // Add assistant response
    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        content: response.message,
        sources: response.sources || [],
        confidence: response.confidence || 0,
        rag_used: response.rag_used || false,
        indexed_chunks: response.indexed_chunks || null,
        graph_used: response.graph_used || false,
        graph_context: response.graph_context || null,
        timestamp: new Date().toISOString(),
        streamed: false,
      },
    ]);

    // Update index status if auto-indexed
    if (response.indexed_chunks > 0) {
      await checkIndexStatus();
    }
  };

  // 🆕 Abort streaming
  const handleAbortStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  // Render message
  const renderMessage = (message, index) => {
    if (message.role === 'user') {
      return (
        <div key={index} className="flex justify-end mb-4">
          <div className="bg-blue-500 text-white rounded-lg px-4 py-2 max-w-[70%]">
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
        </div>
      );
    }

    if (message.role === 'assistant') {
      return (
        <div key={index} className="flex justify-start mb-4">
          <div className="bg-gray-200 text-gray-800 rounded-lg px-4 py-2 max-w-[70%]">
            {/* Message Content */}
            <div className="mb-2 whitespace-pre-wrap prose prose-sm max-w-none">
              {message.content}
            </div>

            {/* Mode Badges */}
            <div className="mt-3 flex flex-wrap gap-2">
              {/* 🆕 Streaming Badge */}
              {message.streamed && (
                <span className="inline-flex items-center gap-1 px-2 py-1 bg-cyan-100 text-cyan-800 rounded text-xs font-medium">
                  🌊 Streamed
                  {message.interrupted && ' (interrupted)'}
                </span>
              )}

              {/* Graph Badge */}
              {message.graph_used && (
                <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-800 rounded text-xs font-medium">
                  🕸️ Graph Used
                  {message.graph_context && (
                    <span className="ml-1 text-green-600">
                      ({message.graph_context})
                    </span>
                  )}
                </span>
              )}

              {/* RAG Badge */}
              {message.rag_used && !message.graph_used && (
                <span className="inline-flex items-center gap-1 px-2 py-1 bg-purple-100 text-purple-800 rounded text-xs font-medium">
                  📚 Vector Search
                </span>
              )}

              {/* Hybrid Badge */}
              {message.rag_used && message.graph_used && (
                <span className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-medium">
                  ⚡ Hybrid RAG
                </span>
              )}

              {/* Auto-indexed Badge */}
              {message.indexed_chunks > 0 && (
                <span className="inline-flex items-center gap-1 px-2 py-1 bg-purple-100 text-purple-800 rounded text-xs font-medium">
                  📚 {message.indexed_chunks} chunks
                </span>
              )}

              {/* Confidence Badge */}
              {message.confidence > 0 && (
                <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${
                  message.confidence >= 0.8
                    ? 'bg-green-100 text-green-800'
                    : message.confidence >= 0.6
                    ? 'bg-yellow-100 text-yellow-800'
                    : 'bg-red-100 text-red-800'
                }`}>
                  {(message.confidence * 100).toFixed(0)}% confident
                </span>
              )}
            </div>

            {/* Sources */}
            {message.sources && message.sources.length > 0 && (
              <div className="mt-3 text-xs">
                <div className="font-semibold text-gray-600 mb-1">Sources:</div>
                <div className="space-y-1">
                  {message.sources.map((source, idx) => (
                    <div key={idx} className="text-gray-500 truncate">
                      📄 {source}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      );
    }

    if (message.role === 'error') {
      return (
        <div key={index} className="flex justify-start mb-4">
          <div className="bg-red-100 text-red-800 rounded-lg px-4 py-2 max-w-[70%]">
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
        </div>
      );
    }

    return null;
  };

  // Search Mode Selector Component
  const SearchModeSelector = () => (
    <div className="space-y-2">
      <button
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="flex items-center justify-between w-full text-sm font-medium text-gray-700 hover:text-gray-900 transition"
      >
        <span>🎯 Search Mode</span>
        <span className="text-xs text-gray-500">
          {showAdvanced ? '▼ Hide' : '▶ Show'}
        </span>
      </button>

      {showAdvanced && (
        <div className="space-y-2 pl-2 border-l-2 border-gray-200">
          {/* Auto Mode */}
          <label className="flex items-start space-x-2 cursor-pointer hover:bg-gray-50 p-2 rounded transition">
            <input
              type="radio"
              value="auto"
              checked={searchMode === 'auto'}
              onChange={(e) => setSearchMode(e.target.value)}
              className="mt-1 text-blue-600 focus:ring-blue-500"
            />
            <div className="flex-1">
              <div className="text-sm font-medium text-gray-900">
                ⚡ Auto (Recommended)
              </div>
              <div className="text-xs text-gray-500">
                Smart routing based on question type
              </div>
            </div>
            {searchMode === 'auto' && (
              <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded font-medium">
                Active
              </span>
            )}
          </label>

          {/* Graph Mode */}
          <label className="flex items-start space-x-2 cursor-pointer hover:bg-gray-50 p-2 rounded transition">
            <input
              type="radio"
              value="graph"
              checked={searchMode === 'graph'}
              onChange={(e) => setSearchMode(e.target.value)}
              className="mt-1 text-green-600 focus:ring-green-500"
            />
            <div className="flex-1">
              <div className="text-sm font-medium text-gray-900">
                🕸️ Graph Search
              </div>
              <div className="text-xs text-gray-500">
                Use Neo4j for code structure, relationships, and history
              </div>
            </div>
            {searchMode === 'graph' && (
              <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded font-medium">
                Active
              </span>
            )}
          </label>

          {/* Vector Mode */}
          <label className="flex items-start space-x-2 cursor-pointer hover:bg-gray-50 p-2 rounded transition">
            <input
              type="radio"
              value="vector"
              checked={searchMode === 'vector'}
              onChange={(e) => setSearchMode(e.target.value)}
              className="mt-1 text-purple-600 focus:ring-purple-500"
            />
            <div className="flex-1">
              <div className="text-sm font-medium text-gray-900">
                📚 Vector Search
              </div>
              <div className="text-xs text-gray-500">
                Use ChromaDB for semantic code search
              </div>
            </div>
            {searchMode === 'vector' && (
              <span className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded font-medium">
                Active
              </span>
            )}
          </label>
        </div>
      )}

      {/* Mode Indicator */}
      {!showAdvanced && (
        <div className="mt-2 text-xs text-gray-600">
          Currently: <span className="font-medium text-gray-900">
            {searchMode === 'auto' ? '⚡ Auto' : searchMode === 'graph' ? '🕸️ Graph' : '📚 Vector'}
          </span>
        </div>
      )}
    </div>
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header with Index Status */}
      <div className="bg-gray-100 p-4 border-b">
        <h2 className="text-xl font-bold mb-2">Chat</h2>

        {selectedRepository && (
          <div className="flex items-center justify-between">
            {/* Index Status */}
            <div className="flex items-center space-x-2">
              {indexStatus ? (
                <>
                  {indexStatus.indexed ? (
                    <span className="text-green-600 text-sm">
                      ✓ Indexed ({indexStatus.total_chunks} chunks)
                    </span>
                  ) : (
                    <span className="text-yellow-600 text-sm">
                      ⚠ Not indexed
                    </span>
                  )}
                </>
              ) : (
                <span className="text-gray-500 text-sm">Checking...</span>
              )}

              {/* Manual Index Button */}
              <button
                onClick={handleManualIndex}
                disabled={isIndexing || (indexStatus && indexStatus.indexed)}
                className="text-xs bg-blue-500 text-white px-2 py-1 rounded disabled:bg-gray-400 hover:bg-blue-600 transition-colors"
              >
                {isIndexing ? 'Indexing...' : 'Index Now'}
              </button>
            </div>

            {/* Feature Toggles */}
            <div className="flex items-center space-x-3 text-sm">
              {/* 🆕 Streaming Toggle */}
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={streamingEnabled}
                  onChange={(e) => setStreamingEnabled(e.target.checked)}
                  className="w-4 h-4 text-cyan-600 rounded"
                />
                <span className="text-gray-700 flex items-center gap-1">
                  🌊 Stream
                </span>
              </label>

              {/* RAG Toggle */}
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={ragEnabled}
                  onChange={(e) => setRagEnabled(e.target.checked)}
                  className="w-4 h-4 text-blue-600 rounded"
                />
                <span className="text-gray-700">RAG</span>
              </label>

              {/* Auto-Index Toggle */}
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoIndex}
                  onChange={(e) => setAutoIndex(e.target.checked)}
                  className="w-4 h-4 text-blue-600 rounded"
                />
                <span className="text-gray-700">Auto-Index</span>
              </label>
            </div>
          </div>
        )}
      </div>

      {/* Search Mode Selector */}
      {selectedRepository && (
        <div className="p-4 bg-gray-50 border-b">
          <SearchModeSelector />
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 bg-white">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 mt-8">
            <div className="text-6xl mb-4">💬</div>
            <p className="text-lg mb-2">Start chatting about the repository!</p>
            {selectedRepository && (
              <div className="mt-4 text-sm text-gray-400">
                <p className="mb-2">Try asking:</p>
                <ul className="space-y-1">
                  <li>"Who are the main contributors?" 🕸️</li>
                  <li>"How does the auth system work?" 📚</li>
                  <li>"What changed in the last commit?" 📝</li>
                  <li>"Show me the hot spots" 🔥</li>
                </ul>
                {streamingEnabled && (
                  <p className="mt-3 text-cyan-600">
                    🌊 Streaming enabled - responses will appear in real-time!
                  </p>
                )}
              </div>
            )}
          </div>
        ) : (
          <>
            {messages.map((message, index) => renderMessage(message, index))}

            {/* 🆕 Streaming Message (in progress) */}
            {isStreaming && streamingMessage && (
              <div className="flex justify-start mb-4">
                <div className="bg-gray-200 text-gray-800 rounded-lg px-4 py-2 max-w-[70%]">
                  <div className="whitespace-pre-wrap prose prose-sm max-w-none">
                    {streamingMessage}
                    <span className="inline-block w-2 h-4 bg-gray-800 ml-1 animate-pulse"></span>
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <span className="text-xs text-cyan-600">🌊 Streaming...</span>
                    <button
                      onClick={handleAbortStreaming}
                      className="text-xs bg-red-500 text-white px-2 py-1 rounded hover:bg-red-600 transition"
                    >
                      Stop
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* Loading indicator (normal mode only) */}
        {loading && !isStreaming && (
          <div className="flex justify-start mb-4">
            <div className="bg-gray-200 text-gray-800 rounded-lg px-4 py-2">
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                <span className="ml-2 text-sm">Thinking...</span>
              </div>
            </div>
          </div>
        )}

        {/* Auto-scroll anchor */}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="bg-gray-100 p-4 border-t">
        <div className="flex space-x-2">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
            placeholder={
              selectedRepository
                ? 'Ask anything about this repository...'
                : 'Select a repository first...'
            }
            disabled={!selectedRepository || loading}
            className="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition"
          />
          <button
            onClick={handleSendMessage}
            disabled={!selectedRepository || loading || !inputMessage.trim()}
            className="bg-blue-500 text-white px-6 py-2 rounded-lg hover:bg-blue-600 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
          >
            {loading ? 'Sending...' : 'Send'}
          </button>
        </div>

        {/* Enhanced Tips */}
        {selectedRepository && (
          <div className="text-xs text-gray-500 mt-2 space-y-1">
            <p>
              <span className="font-medium text-gray-700">Current mode:</span>{' '}
              {searchMode === 'auto' && '⚡ Auto (Smart routing)'}
              {searchMode === 'graph' && '🕸️ Graph (Structure/History)'}
              {searchMode === 'vector' && '📚 Vector (Semantic search)'}
              {streamingEnabled && (
                <span className="text-cyan-600 ml-2">
                  🌊 Streaming enabled
                </span>
              )}
            </p>
            {ragEnabled && (
              <p>💡 RAG enabled: Ask "how to use this library" or "explain this function"</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default EnhancedChatWindow;
