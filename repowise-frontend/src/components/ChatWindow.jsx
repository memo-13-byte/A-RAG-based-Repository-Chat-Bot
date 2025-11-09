import { useState, useRef, useEffect } from "react"
import { Send, Bot, User, Loader2 } from "lucide-react"
import { useMutation } from "@tanstack/react-query"
import { chatAPI } from "../services/api"
import ReactMarkdown from "react-markdown"

export default function ChatWindow({ selectedRepository }) {
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState("")
  const [conversationId, setConversationId] = useState(null)
  const messagesEndRef = useRef(null)

  // Scroll to bottom when new message arrives
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const generateMessageId = () => `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

  // Send message mutation
  const sendMessageMutation = useMutation({
    mutationFn: ({ message, repoUrl, convId }) => chatAPI.sendMessage(message, repoUrl, convId),
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        {
          id: generateMessageId(),
          role: "assistant",
          content: data.message,
          sources: data.sources,
          confidence: data.confidence,
        },
      ])

      // Set conversation ID
      if (data.conversation_id) {
        setConversationId(data.conversation_id)
      }
    },
    onError: (error) => {
      console.error("Error sending message:", error)
      setMessages((prev) => [
        ...prev,
        {
          id: generateMessageId(),
          role: "assistant",
          content: "I am sorry, an error happened. Please try again.",
          isError: true,
        },
      ])
    },
  })

  const handleSendMessage = () => {
    if (!inputMessage.trim() || sendMessageMutation.isPending) return

    const userMessage = {
      id: generateMessageId(),
      role: "user",
      content: inputMessage,
    }
    setMessages((prev) => [...prev, userMessage])

    // Send to API
    sendMessageMutation.mutate({
      message: inputMessage,
      repoUrl: selectedRepository?.url,
      convId: conversationId,
    })

    // Clear input
    setInputMessage("")
  }

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-lg">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-primary-500 to-primary-600">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white">
              {selectedRepository ? selectedRepository.name : "RepoWise Chat"}
            </h2>
            {selectedRepository && <p className="text-sm text-gray-500 mt-1">{selectedRepository.url}</p>}
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && !selectedRepository && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Bot className="w-16 h-16 mx-auto mb-4 text-gray-300" />
            <h3 className="text-lg font-medium text-gray-700 mb-2">Select a repository to start chatting</h3>
            <p className="text-sm text-gray-500">Choose a repository from the left sidebar</p>
          </div>
        )}

        {messages.length === 0 && selectedRepository && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Bot className="w-16 h-16 mx-auto mb-4 text-gray-300" />
            <h3 className="text-lg font-medium text-gray-700 mb-2">Welcome to the RepoWise!</h3>
            <p className="text-sm">Begin to ask question about the Repository...</p>
          </div>
        )}

        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`flex items-start space-x-3 max-w-3xl ${
                message.role === "user" ? "flex-row-reverse space-x-reverse" : ""
              }`}
            >
              {/* Avatar */}
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  message.role === "user" ? "bg-primary-500" : message.isError ? "bg-red-500" : "bg-gray-200"
                }`}
              >
                {message.role === "user" ? (
                  <User className="w-5 h-5 text-white" />
                ) : (
                  <Bot className={`w-5 h-5 ${message.isError ? "text-white" : "text-gray-600"}`} />
                )}
              </div>

              {/* Message Content */}
              <div
                className={`px-4 py-3 rounded-lg ${
                  message.role === "user"
                    ? "bg-primary-500 text-white"
                    : message.isError
                      ? "bg-red-50 text-red-900 border border-red-200"
                      : "bg-gray-100 text-gray-900"
                }`}
              >
                <div className="prose prose-sm max-w-none">
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>

                {/* Sources and Confidence */}
                {message.sources && message.sources.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <p className="text-xs text-gray-500 mb-2">Sources:</p>
                    <div className="flex flex-wrap gap-2">
                      {message.sources.map((source) => (
                        <span key={source} className="text-xs bg-white px-2 py-1 rounded border border-gray-300">
                          {source}
                        </span>
                      ))}
                    </div>
                    {message.confidence && (
                      <p className="text-xs text-gray-500 mt-2">Confidence: {(message.confidence * 100).toFixed(0)}%</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {sendMessageMutation.isPending && (
          <div className="flex justify-start">
            <div className="flex items-start space-x-3">
              <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
                <Bot className="w-5 h-5 text-gray-600" />
              </div>
              <div className="bg-gray-100 px-4 py-3 rounded-lg">
                <Loader2 className="w-5 h-5 animate-spin text-gray-600" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-gray-200">
        <div className="flex space-x-2">
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder={selectedRepository ? "Ask a question about the repository..." : "Select a repository first..."}
            disabled={!selectedRepository || sendMessageMutation.isPending}
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none text-sm disabled:bg-gray-50 disabled:cursor-not-allowed"
            rows={3}
          />
          <button
            onClick={handleSendMessage}
            disabled={!selectedRepository || !inputMessage.trim() || sendMessageMutation.isPending}
            className="px-6 py-3 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
          >
            {sendMessageMutation.isPending ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
