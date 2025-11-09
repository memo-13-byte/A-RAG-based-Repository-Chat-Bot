import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ChatWindow from './components/ChatWindow';
import RepositorySelector from './components/RepositorySelector';

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
                  <p className="text-sm text-gray-500">RAG-Based Repository Chatbot</p>
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
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg-px-8 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-180px)]">
            {/*Repository Selector - Left Sidebar */}
            <div className="lg:col-span-1">
              <RepositorySelector
                onSelectRepository={setSelectedRepository}
                selectedRepository={selectedRepository}
              />
            </div>

            {/* Chat Window - Main Area */}
            <div className="lg:col-span-2">
              <ChatWindow selectedRepository={selectedRepository} />
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
