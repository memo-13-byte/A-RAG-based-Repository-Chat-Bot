"use client"

import { useState } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import ChatWindow from "./components/ChatWindow"
import RepositorySelector from "./components/RepositorySelector"
import GraphVisualization from "./components/GraphVisualization"
import AutoFix from "./components/Autofix"

// React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function App() {
  const [selectedRepository, setSelectedRepository] = useState(null)
  const [activeTab, setActiveTab] = useState("chat")

  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex flex-col min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
        {/* Header */}
        <header className="bg-white shadow-sm flex-shrink-0">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-xl">R</span>
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">RepoWise</h1>
                  <p className="text-sm text-gray-500">RAG-Based Repository Chatbot with Graph AI & AutoFix</p>
                </div>
              </div>
              <div className="flex items-center space-x-2 text-sm text-gray-600">
                <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full font-medium">Online</span>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 flex">
          <div className="flex flex-col lg:flex-row gap-6 w-full">
            {/* Repository Selector - Left Sidebar */}
            <div className="lg:w-1/3 flex-shrink-0">
              <RepositorySelector onSelectRepository={setSelectedRepository} selectedRepository={selectedRepository} />
            </div>

            {/* Main Area - Chat, Graph, or AutoFix */}
            <div className="lg:w-2/3 flex-1 flex flex-col min-h-0">
              {/* Tab Navigation */}
              <div className="mb-4 bg-white rounded-lg shadow-sm flex-shrink-0">
                <div className="flex border-b border-gray-200">
                  <button
                    onClick={() => setActiveTab("chat")}
                    className={`flex-1 px-6 py-3 font-medium text-sm transition-colors ${
                      activeTab === "chat"
                        ? "border-b-2 border-blue-600 text-blue-600 bg-blue-50"
                        : "text-gray-600 hover:text-gray-800 hover:bg-gray-50"
                    }`}
                  >
                    Chat
                  </button>
                  <button
                    onClick={() => setActiveTab("graph")}
                    className={`flex-1 px-6 py-3 font-medium text-sm transition-colors ${
                      activeTab === "graph"
                        ? "border-b-2 border-blue-600 text-blue-600 bg-blue-50"
                        : "text-gray-600 hover:text-gray-800 hover:bg-gray-50"
                    }`}
                  >
                    Code Graph
                  </button>
                  <button
                    onClick={() => setActiveTab("autofix")}
                    className={`flex-1 px-6 py-3 font-medium text-sm transition-colors ${
                      activeTab === "autofix"
                        ? "border-b-2 border-purple-600 text-purple-600 bg-purple-50"
                        : "text-gray-600 hover:text-gray-800 hover:bg-gray-50"
                    }`}
                  >
                    AutoFix
                  </button>
                </div>
              </div>

              {/* Content Area - Conditional Rendering */}
              <div className="flex-1 bg-white rounded-lg shadow-sm overflow-hidden min-h-0">
                {activeTab === "chat" ? (
                  <ChatWindow selectedRepository={selectedRepository} />
                ) : activeTab === "graph" ? (
                  <GraphVisualization selectedRepository={selectedRepository} />
                ) : (
                  <AutoFix selectedRepository={selectedRepository} />
                )}
              </div>
            </div>
          </div>
        </main>

        {/* Footer */}
        <footer className="flex-shrink-0 text-center py-4 text-sm text-gray-500 bg-white border-t border-gray-200">
          <p>BBM479 Graduation Project - Hacettepe University CS/AI</p>
        </footer>
      </div>
    </QueryClientProvider>
  )
}

export default App
