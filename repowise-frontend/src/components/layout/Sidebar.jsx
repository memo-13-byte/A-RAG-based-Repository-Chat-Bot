import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { repositoryAPI } from '../../services/api';
import api from '../../services/api';
import { useAppStore } from '../../stores/app-store';
import { useThemeStore } from '../../stores/theme-store';
import { cn } from '../../lib/utils';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import { Skeleton } from '../ui/skeleton';
import {
  MessageSquare,
  Network,
  Sparkles,
  Github,
  Search,
  Plus,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
  Monitor,
  Loader2,
  Star,
  GitBranch,
  CheckCircle2,
  AlertCircle,
  FolderGit2,
} from 'lucide-react';

const navItems = [
  { id: 'chat', label: 'Chat', icon: MessageSquare, description: 'Ask questions about code' },
  { id: 'graph', label: 'Code Graph', icon: Network, description: 'Visualize code structure' },
  { id: 'autofix', label: 'AutoFix', icon: Sparkles, description: 'AI-powered code fixes' },
];

export default function Sidebar() {
  const [repoUrl, setRepoUrl] = useState('');
  const [showAddRepo, setShowAddRepo] = useState(false);
  
  const { 
    selectedRepository, 
    setSelectedRepository, 
    activeView, 
    setActiveView,
    sidebarCollapsed,
    toggleSidebar 
  } = useAppStore();
  
  const { theme, setTheme } = useThemeStore();

  const { data: repositories, isLoading: reposLoading, refetch } = useQuery({
    queryKey: ['repositories'],
    queryFn: repositoryAPI.listRepositories,
  });

  const analyzeRepoMutation = useMutation({
    mutationFn: (url) => repositoryAPI.analyzeRepository(url),
    onSuccess: (data) => {
      setRepoUrl('');
      setShowAddRepo(false);
      refetch();
      if (data.repository) {
        setSelectedRepository(data.repository);
      }
    },
  });

  const analyzeGraphMutation = useMutation({
    mutationFn: async (repoUrl) => {
      const response = await api.post('/api/graph/analyze', null, {
        params: { repository_url: repoUrl }
      });
      return response.data;
    },
  });

  const handleAnalyze = (e) => {
    e.preventDefault();
    if (!repoUrl.trim()) return;
    analyzeRepoMutation.mutate(repoUrl);
  };

  const getThemeIcon = () => {
    switch (theme) {
      case 'dark': return Moon;
      case 'light': return Sun;
      default: return Monitor;
    }
  };

  const cycleTheme = () => {
    const themes = ['light', 'dark', 'system'];
    const currentIndex = themes.indexOf(theme);
    const nextIndex = (currentIndex + 1) % themes.length;
    setTheme(themes[nextIndex]);
  };

  const ThemeIcon = getThemeIcon();

  return (
    <aside
      className={cn(
        "flex flex-col h-full bg-sidebar-background border-r border-sidebar-border transition-all duration-300",
        sidebarCollapsed ? "w-16" : "w-72"
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-sidebar-border">
        {!sidebarCollapsed && (
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-br from-primary to-primary/70 rounded-lg flex items-center justify-center shadow-md">
              <span className="text-primary-foreground font-bold text-lg">R</span>
            </div>
            <div>
              <h1 className="font-bold text-sidebar-foreground">RepoWise</h1>
              <p className="text-xs text-muted-foreground">RAG + Graph AI</p>
            </div>
          </div>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleSidebar}
          className="text-sidebar-foreground hover:bg-sidebar-accent"
        >
          {sidebarCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>

      {/* Navigation */}
      <nav className="p-2 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          return (
            <Button
              key={item.id}
              variant={isActive ? "secondary" : "ghost"}
              className={cn(
                "w-full justify-start gap-3",
                sidebarCollapsed && "justify-center px-2",
                isActive && "bg-sidebar-accent text-sidebar-accent-foreground"
              )}
              onClick={() => setActiveView(item.id)}
            >
              <Icon className={cn("h-4 w-4", isActive && "text-sidebar-primary")} />
              {!sidebarCollapsed && (
                <span className="truncate">{item.label}</span>
              )}
            </Button>
          );
        })}
      </nav>

      {/* Repository Section */}
      {!sidebarCollapsed && (
        <div className="flex-1 flex flex-col min-h-0 border-t border-sidebar-border">
          <div className="p-3 flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Repositories
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => setShowAddRepo(!showAddRepo)}
            >
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>

          {/* Add Repository Form */}
          {showAddRepo && (
            <form onSubmit={handleAnalyze} className="px-3 pb-3 space-y-2">
              <Input
                type="text"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/user/repo"
                className="h-8 text-sm"
                disabled={analyzeRepoMutation.isPending}
              />
              <Button
                type="submit"
                size="sm"
                className="w-full"
                disabled={!repoUrl.trim() || analyzeRepoMutation.isPending}
              >
                {analyzeRepoMutation.isPending ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Search className="h-3.5 w-3.5" />
                    Analyze
                  </>
                )}
              </Button>
              {analyzeRepoMutation.isError && (
                <p className="text-xs text-destructive flex items-center gap-1">
                  <AlertCircle className="h-3 w-3" />
                  {analyzeRepoMutation.error?.response?.data?.detail || 'Failed to analyze'}
                </p>
              )}
              {analyzeRepoMutation.isSuccess && (
                <p className="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  Repository added
                </p>
              )}
            </form>
          )}

          {/* Repository List */}
          <ScrollArea className="flex-1 px-2">
            {reposLoading ? (
              <div className="space-y-2 p-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="p-3 rounded-lg border border-sidebar-border">
                    <Skeleton className="h-4 w-3/4 mb-2" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                ))}
              </div>
            ) : repositories && repositories.length > 0 ? (
              <div className="space-y-1 pb-2">
                {repositories.map((repo) => {
                  const isSelected = selectedRepository?.id === repo.id;
                  return (
                    <button
                      key={repo.id}
                      onClick={() => setSelectedRepository(repo)}
                      className={cn(
                        "w-full text-left p-3 rounded-lg transition-all",
                        "hover:bg-sidebar-accent/50",
                        isSelected && "bg-sidebar-accent border border-sidebar-primary/30"
                      )}
                    >
                      <div className="flex items-start gap-2">
                        <FolderGit2 className={cn(
                          "h-4 w-4 mt-0.5 shrink-0",
                          isSelected ? "text-sidebar-primary" : "text-muted-foreground"
                        )} />
                        <div className="flex-1 min-w-0">
                          <p className={cn(
                            "font-medium text-sm truncate",
                            isSelected ? "text-sidebar-foreground" : "text-sidebar-foreground/80"
                          )}>
                            {repo.full_name}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                              {repo.language || 'Unknown'}
                            </Badge>
                            <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
                              <Star className="h-2.5 w-2.5" />
                              {repo.stars?.toLocaleString() || 0}
                            </span>
                          </div>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="p-4 text-center">
                <Github className="h-8 w-8 mx-auto text-muted-foreground/50 mb-2" />
                <p className="text-xs text-muted-foreground">No repositories yet</p>
                <p className="text-[10px] text-muted-foreground/70 mt-1">Add one above to get started</p>
              </div>
            )}
          </ScrollArea>
        </div>
      )}

      {/* Footer */}
      <div className={cn(
        "border-t border-sidebar-border p-3",
        sidebarCollapsed ? "flex justify-center" : "flex items-center justify-between"
      )}>
        <Button
          variant="ghost"
          size="icon"
          onClick={cycleTheme}
          className="text-sidebar-foreground hover:bg-sidebar-accent"
        >
          <ThemeIcon className="h-4 w-4" />
        </Button>
        {!sidebarCollapsed && (
          <div className="flex items-center gap-2">
            <Badge variant="success" className="text-[10px]">
              Online
            </Badge>
          </div>
        )}
      </div>
    </aside>
  );
}
