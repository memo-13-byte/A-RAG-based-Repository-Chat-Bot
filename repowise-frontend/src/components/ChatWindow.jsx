import React, { useState, useEffect } from 'react';
import { chatAPI, repositoryAPI, ragAPI, isRAGAvailable } from '../services/api';

/**
 * Enhanced Chat Window Component - Phase 3
 *
 * New Features:
 * - RAG-powered responses for code questions
 * - Auto-indexing capability
 * - Index status display
 * - Semantic code search
 * - Graph context integration (NEW!)
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
  const [useGraph, setUseGraph] = useState(true);  // Graph context toggle

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

  // Send message with Phase 3 features
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
      // Phase 3: Send with graph context
      const response = await chatAPI.sendMessage(
        userMessage,
        selectedRepository.url,
        conversationId,
        ragEnabled,
        autoIndex,
        useGraph  // Pass graph toggle state
      );

      // Save conversation ID
      if (!conversationId) {
        setConversationId(response.conversation_id);
      }

      // Add assistant response to chat
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
        },
      ]);

      // Update index status if auto-indexed
      if (response.indexed_chunks > 0) {
        await checkIndexStatus();
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
    }
  };

  // Render message with Phase 3 metadata (including graph context)
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
            <p className="mb-2 whitespace-pre-wrap">{message.content}</p>

            {/* Phase 3: Graph Context Display - NEW! */}
            {message.graph_used && message.graph_context && (
              <div className="mt-3 p-3 bg-blue-50 rounded-lg border border-blue-200">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-semibold text-blue-800">
                    🔗 Graph Enhanced
                  </span>
                </div>
                <div className="text-xs text-blue-900 whitespace-pre-wrap">
                  {message.graph_context}
                </div>
              </div>
            )}

            {/* Phase 2: Show RAG metadata */}
            <div className="mt-2 pt-2 border-t border-gray-300 text-xs">
              {/* RAG Status */}
              {message.rag_used && (
                <div className="mb-1 text-green-600 font-semibold">
                  ✓ RAG-Powered Response
                </div>
              )}

              {/* Graph Status - NEW! */}
              {message.graph_used && (
                <div className="mb-1 text-blue-600 font-semibold">
                  📊 Graph Context Used
                </div>
              )}

              {/* Auto-indexed indicator */}
              {message.indexed_chunks > 0 && (
                <div className="mb-1 text-purple-600">
                  📚 Auto-indexed: {message.indexed_chunks} chunks
                </div>
              )}

              {/* Confidence Score */}
              {message.confidence > 0 && (
                <div className="mb-1">
                  Confidence: {(message.confidence * 100).toFixed(0)}%
                </div>
              )}

              {/* Sources */}
              {message.sources && message.sources.length > 0 && (
                <div className="mt-1">
                  <strong>Sources:</strong>
                  <ul className="list-disc list-inside">
                    {message.sources.map((source, idx) => (
                      <li key={idx} className="text-gray-700">{source}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
      );
    }

    if (message.role === 'error') {
      return (
        <div key={index} className="flex justify-start mb-4">
          <div className="bg-red-100 text-red-800 rounded-lg px-4 py-2 max-w-[70%] border border-red-300">
            <p>{message.content}</p>
          </div>
        </div>
      );
    }

    return null;
  };

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
                className="text-xs bg-blue-500 text-white px-2 py-1 rounded disabled:bg-gray-400"
              >
                {isIndexing ? 'Indexing...' : 'Index Now'}
              </button>
            </div>

            {/* Feature Toggles */}
            <div className="flex items-center space-x-3 text-sm">
              {/* RAG Toggle */}
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={ragEnabled}
                  onChange={(e) => setRagEnabled(e.target.checked)}
                  className="w-4 h-4 text-blue-600 rounded"
                />
                <span className="text-gray-700">RAG Mode</span>
              </label>

              {/* Graph Toggle - NEW! */}
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useGraph}
                  onChange={(e) => setUseGraph(e.target.checked)}
                  className="w-4 h-4 text-blue-600 rounded"
                />
                <span className="text-gray-700">Graph Context</span>
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

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 mt-8">
            <p className="text-lg mb-2">No messages yet. Start a conversation!</p>
            {ragEnabled && selectedRepository && (
              <p className="text-sm mt-2">
                💡 RAG mode is enabled. Ask questions about code!
              </p>
            )}
            {useGraph && selectedRepository && (
              <p className="text-sm text-blue-600 mt-1">
                📊 Graph context is enabled. Ask about class relationships!
              </p>
            )}
          </div>
        ) : (
          messages.map((message, index) => renderMessage(message, index))
        )}

        {loading && (
          <div className="flex justify-start mb-4">
            <div className="bg-gray-200 text-gray-800 rounded-lg px-4 py-2">
              <p>Thinking...</p>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="bg-gray-100 p-4 border-t">
        <div className="flex space-x-2">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder={
              selectedRepository
                ? 'Ask anything about this repository...'
                : 'Select a repository first...'
            }
            disabled={!selectedRepository || loading}
            className="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={handleSendMessage}
            disabled={!selectedRepository || loading || !inputMessage.trim()}
            className="bg-blue-500 text-white px-6 py-2 rounded-lg hover:bg-blue-600 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>

        {/* Tips */}
        {selectedRepository && (
          <div className="text-xs text-gray-500 mt-2 space-y-1">
            {ragEnabled && (
              <p>💡 RAG Mode: Ask "how to use this library" or "explain this function"</p>
            )}
            {useGraph && (
              <p>📊 Graph Mode: Ask "what classes inherit from X" or "show dependencies"</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default EnhancedChatWindow;