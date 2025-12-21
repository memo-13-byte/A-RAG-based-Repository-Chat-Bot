import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ChatWindow from './components/ChatWindow';
import RepositorySelector from './components/RepositorySelector';
import GraphVisualization from './components/GraphVisualization';  // ← NEW IMPORT

// React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  const [selectedRepository, setSelectedRepository] = useState(null);
  const [activeTab, setActiveTab] = useState('chat');  // ← NEW STATE: 'chat' or 'graph'

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
        {/* Header */}
        <header className="bg-white shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-xl">R</span>
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-gray-900">RepoWise</h1>
                  <p className="text-sm text-gray-500">RAG-Based Repository Chatbot with Graph AI</p>
                </div>
              </div>
              <div className="flex items-center space-x-2 text-sm text-gray-600">
                <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full font-medium">
                  Online
                </span>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-180px)]">
            {/* Repository Selector - Left Sidebar */}
            <div className="lg:col-span-1">
              <RepositorySelector
                onSelectRepository={setSelectedRepository}
                selectedRepository={selectedRepository}
              />
            </div>

            {/* Main Area - Chat or Graph */}
            <div className="lg:col-span-2 flex flex-col">
              {/* Tab Navigation - NEW! */}
              <div className="mb-4 bg-white rounded-lg shadow-sm">
                <div className="flex border-b border-gray-200">
                  <button
                    onClick={() => setActiveTab('chat')}
                    className={`flex-1 px-6 py-3 font-medium text-sm transition-colors ${
                      activeTab === 'chat'
                        ? 'border-b-2 border-blue-600 text-blue-600 bg-blue-50'
                        : 'text-gray-600 hover:text-gray-800 hover:bg-gray-50'
                    }`}
                  >
                    💬 Chat
                  </button>
                  <button
                    onClick={() => setActiveTab('graph')}
                    className={`flex-1 px-6 py-3 font-medium text-sm transition-colors ${
                      activeTab === 'graph'
                        ? 'border-b-2 border-blue-600 text-blue-600 bg-blue-50'
                        : 'text-gray-600 hover:text-gray-800 hover:bg-gray-50'
                    }`}
                  >
                    📊 Code Graph
                  </button>
                </div>
              </div>

              {/* Content Area - Conditional Rendering */}
              <div className="flex-1 bg-white rounded-lg shadow-sm overflow-hidden">
                {activeTab === 'chat' ? (
                  <ChatWindow selectedRepository={selectedRepository} />
                ) : (
                  <GraphVisualization selectedRepository={selectedRepository} />
                )}
              </div>
            </div>
          </div>
        </main>

        {/* Footer */}
        <footer className="text-center py-4 text-sm text-gray-500">
          <p>
            BBM479 Graduation Project - Hacettepe University CS/AI
          </p>
        </footer>
      </div>
    </QueryClientProvider>
  );
}

export default App;