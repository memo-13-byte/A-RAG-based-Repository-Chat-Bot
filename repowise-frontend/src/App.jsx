import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import Sidebar from "./components/layout/Sidebar";
import ChatWindow from "./components/ChatWindow";
import GraphVisualization from "./components/GraphVisualization";
import AutoFix from "./components/Autofix";
import { useAppStore } from "./stores/app-store";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function MainContent() {
  const { activeView, selectedRepository } = useAppStore();

  return (
    <main className="flex-1 flex flex-col min-h-0 bg-background">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-border bg-card/50">
        <div>
          <h1 className="text-xl font-semibold text-foreground">
            {activeView === 'chat' && 'Chat'}
            {activeView === 'graph' && 'Code Graph'}
            {activeView === 'autofix' && 'AutoFix'}
          </h1>
          {selectedRepository && (
            <p className="text-sm text-muted-foreground">
              {selectedRepository.full_name}
            </p>
          )}
        </div>
        {!selectedRepository && (
          <p className="text-sm text-muted-foreground">
            Select a repository from the sidebar to get started
          </p>
        )}
      </header>

      {/* Content Area */}
      <div className="flex-1 min-h-0">
        {activeView === 'chat' && (
          <ChatWindow selectedRepository={selectedRepository} />
        )}
        {activeView === 'graph' && (
          <GraphVisualization selectedRepository={selectedRepository} />
        )}
        {activeView === 'autofix' && (
          <AutoFix selectedRepository={selectedRepository} />
        )}
      </div>
    </main>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="flex h-screen bg-background">
        <Sidebar />
        <MainContent />
      </div>
      <Toaster 
        position="bottom-right"
        toastOptions={{
          className: "bg-card text-card-foreground border-border",
        }}
      />
    </QueryClientProvider>
  );
}

export default App;
