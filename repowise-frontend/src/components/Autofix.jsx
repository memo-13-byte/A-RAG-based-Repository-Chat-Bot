import { useState, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { toast } from 'sonner';
import { autofixAPI } from '../services/api';
import { useThemeStore } from '../stores/theme-store';
import { cn } from '../lib/utils';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { ScrollArea } from './ui/scroll-area';
import { Skeleton } from './ui/skeleton';
import {
  Sparkles,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Download,
  X,
  Lightbulb,
  Zap,
  RefreshCw,
  ExternalLink,
  Terminal,
} from 'lucide-react';

const MODELS = [
  { value: 'gpt-4o-mini-2024-07-18', label: 'GPT-4o Mini', description: 'Fast and efficient' },
  { value: 'gpt-4o-2024-08-06', label: 'GPT-4o', description: 'Balanced performance' },
  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo', description: 'Advanced reasoning' },
];

// Status Badge Component
function StatusBadge({ status }) {
  const config = {
    processing: { variant: 'info', icon: Clock, label: 'Processing' },
    running: { variant: 'warning', icon: Loader2, label: 'Analyzing', animate: true },
    completed: { variant: 'success', icon: CheckCircle2, label: 'Completed' },
    failed: { variant: 'destructive', icon: XCircle, label: 'Failed' },
  };

  const { variant, icon: Icon, label, animate } = config[status] || config.processing;

  return (
    <Badge variant={variant} className="gap-1.5">
      <Icon className={cn("h-3 w-3", animate && "animate-spin")} />
      {label}
    </Badge>
  );
}

// Progress Steps Component
function ProgressSteps({ status }) {
  const steps = [
    { id: 'clone', label: 'Repository cloned', completed: true },
    { id: 'analyze', label: 'Analyzing code structure', completed: status === 'running' || status === 'completed' },
    { id: 'generate', label: 'Generating fix with AI', completed: status === 'completed' },
  ];

  return (
    <div className="space-y-2">
      {steps.map((step) => (
        <div key={step.id} className="flex items-center gap-2">
          <div className={cn(
            "w-2 h-2 rounded-full transition-colors",
            step.completed ? "bg-emerald-500" : "bg-muted-foreground/30",
            !step.completed && status !== 'completed' && status !== 'failed' && "animate-pulse"
          )} />
          <span className={cn(
            "text-sm",
            step.completed ? "text-foreground" : "text-muted-foreground"
          )}>
            {step.label}
          </span>
        </div>
      ))}
    </div>
  );
}

// Patch Preview Modal
function PatchModal({ patch, loading, onClose, taskId }) {
  const [copied, setCopied] = useState(false);
  const { theme } = useThemeStore();
  const isDark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(patch, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success('Copied to clipboard');
  };

  return (
    <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-4xl max-h-[90vh] flex flex-col">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <div>
            <CardTitle>Patch Preview</CardTitle>
            <CardDescription>Task ID: {taskId}</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleCopy}>
              {copied ? <Check className="h-4 w-4 mr-1" /> : <Copy className="h-4 w-4 mr-1" />}
              {copied ? 'Copied' : 'Copy'}
            </Button>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex-1 min-h-0 pb-6">
          <ScrollArea className="h-full max-h-[60vh]">
            {loading ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-5/6" />
              </div>
            ) : patch?.error ? (
              <div className="text-center py-8">
                <AlertCircle className="h-8 w-8 mx-auto text-destructive mb-2" />
                <p className="text-sm text-destructive">{patch.error}</p>
                {patch.path && (
                  <p className="text-xs text-muted-foreground mt-2 font-mono">{patch.path}</p>
                )}
              </div>
            ) : (
              <SyntaxHighlighter
                language="json"
                style={isDark ? oneDark : oneLight}
                customStyle={{ margin: 0, borderRadius: '0.5rem', fontSize: '0.75rem' }}
              >
                {JSON.stringify(patch, null, 2)}
              </SyntaxHighlighter>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}

// How It Works Guide
function HowItWorksGuide({ isHealthy }) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Lightbulb className="h-5 w-5 text-amber-500" />
          How It Works
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-3">
          {[
            { step: 1, title: 'Submit Issue', description: 'Describe the bug or improvement you want' },
            { step: 2, title: 'AI Analysis', description: 'AutoCodeRover analyzes your codebase' },
            { step: 3, title: 'Get Patch', description: 'Receive a ready-to-apply code fix' },
          ].map((item) => (
            <div key={item.step} className="flex gap-3">
              <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                <span className="text-xs font-bold text-primary">{item.step}</span>
              </div>
              <div>
                <p className="text-sm font-medium">{item.title}</p>
                <p className="text-xs text-muted-foreground">{item.description}</p>
              </div>
            </div>
          ))}
        </div>

        <div className={cn(
          "p-3 rounded-lg border",
          isHealthy 
            ? "bg-emerald-500/10 border-emerald-500/20" 
            : "bg-destructive/10 border-destructive/20"
        )}>
          <div className="flex items-center gap-2 mb-1">
            <div className={cn(
              "w-2 h-2 rounded-full",
              isHealthy ? "bg-emerald-500" : "bg-destructive"
            )} />
            <span className="text-sm font-medium">
              {isHealthy ? 'Service Online' : 'Service Offline'}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            {isHealthy 
              ? 'AutoFix is ready to process your requests' 
              : 'Please ensure the backend service is running'}
          </p>
        </div>

        <Card className="bg-muted/50">
          <CardContent className="p-3">
            <p className="text-xs font-semibold text-muted-foreground mb-2">Example Issues</p>
            <ul className="text-xs space-y-1.5 text-muted-foreground">
              <li className="flex items-start gap-2">
                <Terminal className="h-3 w-3 mt-0.5 shrink-0" />
                Add type hints to the main() function
              </li>
              <li className="flex items-start gap-2">
                <Terminal className="h-3 w-3 mt-0.5 shrink-0" />
                Fix the bug in user authentication logic
              </li>
              <li className="flex items-start gap-2">
                <Terminal className="h-3 w-3 mt-0.5 shrink-0" />
                Refactor database connection to use pooling
              </li>
              <li className="flex items-start gap-2">
                <Terminal className="h-3 w-3 mt-0.5 shrink-0" />
                Add error handling to API endpoints
              </li>
            </ul>
          </CardContent>
        </Card>
      </CardContent>
    </Card>
  );
}

// Status Display Component
function StatusDisplay({ taskId, status, onReset, onViewPatch, onDownloadPatch }) {
  const config = {
    processing: {
      color: 'bg-sky-500/10 border-sky-500/20',
      description: 'Preparing your fix request...',
    },
    running: {
      color: 'bg-amber-500/10 border-amber-500/20',
      description: 'AI is analyzing the code and generating a fix...',
    },
    completed: {
      color: 'bg-emerald-500/10 border-emerald-500/20',
      description: 'Fix generated successfully!',
    },
    failed: {
      color: 'bg-destructive/10 border-destructive/20',
      description: 'Failed to generate fix',
    },
  };

  const { color, description } = config[status?.status] || config.processing;

  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle>Fix Status</CardTitle>
        {(status?.status === 'completed' || status?.status === 'failed') && (
          <Button variant="ghost" size="sm" onClick={onReset}>
            <RefreshCw className="h-4 w-4 mr-1" />
            New Fix
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Status Card */}
        <div className={cn("p-4 rounded-lg border", color)}>
          <div className="flex items-center justify-between mb-3">
            <StatusBadge status={status?.status || 'processing'} />
          </div>
          <p className="text-sm text-muted-foreground mb-3">{description}</p>
          <p className="text-xs text-muted-foreground">
            Task ID: <code className="bg-background px-1.5 py-0.5 rounded text-[10px]">{taskId}</code>
          </p>
        </div>

        {/* Error Display */}
        {status?.status === 'failed' && status?.error && (
          <Card className="border-destructive/50">
            <CardContent className="p-3">
              <p className="text-sm font-medium text-destructive mb-1">Error</p>
              <p className="text-xs text-destructive/80">{status.error}</p>
            </CardContent>
          </Card>
        )}

        {/* Success Actions */}
        {status?.status === 'completed' && status?.patch_path && (
          <div className="space-y-3">
            <Card className="border-emerald-500/50">
              <CardContent className="p-3">
                <p className="text-sm font-medium text-emerald-600 dark:text-emerald-400 mb-1">Patch Generated</p>
                <p className="text-xs text-muted-foreground font-mono break-all">{status.patch_path}</p>
              </CardContent>
            </Card>
            <div className="grid grid-cols-2 gap-2">
              <Button onClick={onDownloadPatch} className="w-full">
                <Download className="h-4 w-4 mr-1" />
                Download
              </Button>
              <Button variant="outline" onClick={onViewPatch} className="w-full">
                <ExternalLink className="h-4 w-4 mr-1" />
                Preview
              </Button>
            </div>
          </div>
        )}

        {/* Progress Steps */}
        {(status?.status === 'processing' || status?.status === 'running') && (
          <>
            <ProgressSteps status={status?.status} />
            <Card className="bg-muted/50">
              <CardContent className="p-3">
                <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5" />
                  Estimated: 10 seconds to 10 minutes
                </p>
              </CardContent>
            </Card>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// Main Component
export default function AutoFix({ selectedRepository }) {
  const [repoUrl, setRepoUrl] = useState('');
  const [issueDescription, setIssueDescription] = useState('');
  const [model, setModel] = useState('gpt-4o-mini-2024-07-18');
  const [temperature, setTemperature] = useState(0.2);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState(null);
  const [pollingEnabled, setPollingEnabled] = useState(false);
  const [showPatchModal, setShowPatchModal] = useState(false);
  const [patchContent, setPatchContent] = useState(null);
  const [loadingPatch, setLoadingPatch] = useState(false);

  useEffect(() => {
    if (selectedRepository?.url) {
      setRepoUrl(selectedRepository.url);
    }
  }, [selectedRepository]);

  // Health check
  const { data: healthData, isLoading: healthLoading } = useQuery({
    queryKey: ['autofix-health'],
    queryFn: () => autofixAPI.checkHealth(),
    retry: 1,
    refetchInterval: 30000,
  });

  // Submit mutation
  const submitMutation = useMutation({
    mutationFn: autofixAPI.submitFix,
    onSuccess: (data) => {
      setCurrentTaskId(data.task_id);
      setPollingEnabled(true);
      toast.success('Fix request submitted');
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to submit fix request');
    },
  });

  // Status polling
  const { data: statusData, refetch: refetchStatus } = useQuery({
    queryKey: ['autofix-status', currentTaskId],
    queryFn: () => autofixAPI.getStatus(currentTaskId),
    enabled: pollingEnabled && !!currentTaskId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'completed' || status === 'failed') {
        setPollingEnabled(false);
        if (status === 'completed') toast.success('Fix generated successfully!');
        if (status === 'failed') toast.error('Failed to generate fix');
        return false;
      }
      return 5000;
    },
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    submitMutation.mutate({ repoUrl, issueDescription, model, temperature });
  };

  const handleReset = () => {
    setCurrentTaskId(null);
    setPollingEnabled(false);
    setIssueDescription('');
    submitMutation.reset();
    setPatchContent(null);
  };

  const handleViewPatch = async () => {
    if (!statusData?.patch_path) return;
    setLoadingPatch(true);
    setShowPatchModal(true);

    try {
      const response = await fetch(statusData.patch_path);
      const data = await response.json();
      setPatchContent(data);
    } catch (error) {
      setPatchContent({
        error: 'Could not load patch content',
        path: statusData.patch_path,
      });
    } finally {
      setLoadingPatch(false);
    }
  };

  const handleDownloadPatch = () => {
    if (!statusData?.patch_path) return;
    const link = document.createElement('a');
    link.href = statusData.patch_path;
    link.download = `patch_${currentTaskId}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success('Patch downloaded');
  };

  const isHealthy = healthData?.healthy;
  const isSubmitting = submitMutation.isPending;
  const isFormValid = repoUrl.trim() !== '' && issueDescription.trim().length >= 10;

  if (!selectedRepository) {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
            <Sparkles className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold mb-2">No Repository Selected</h3>
          <p className="text-sm text-muted-foreground">
            Select a repository from the sidebar to use AutoFix
          </p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="h-full flex flex-col p-6 overflow-y-auto">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center shadow-md">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold">AutoFix</h2>
              <p className="text-sm text-muted-foreground">AI-powered automated code fixing</p>
            </div>
          </div>

          {/* Service Status */}
          {!healthLoading && (
            <div className={cn(
              "mt-4 p-3 rounded-lg border flex items-center gap-2",
              isHealthy 
                ? "bg-emerald-500/10 border-emerald-500/20" 
                : "bg-destructive/10 border-destructive/20"
            )}>
              <div className={cn(
                "w-2 h-2 rounded-full",
                isHealthy ? "bg-emerald-500" : "bg-destructive"
              )} />
              <span className={cn(
                "text-sm font-medium",
                isHealthy ? "text-emerald-700 dark:text-emerald-400" : "text-destructive"
              )}>
                {isHealthy ? 'AutoFix Service Online' : 'AutoFix Service Offline'}
              </span>
            </div>
          )}
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1">
          {/* Left: Form */}
          <Card>
            <CardHeader>
              <CardTitle>Submit Fix Request</CardTitle>
              <CardDescription>Describe the issue you want to fix</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Repository URL */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Repository URL</label>
                  <Input
                    type="url"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    placeholder="https://github.com/user/repo.git"
                    disabled={isSubmitting}
                    required
                  />
                </div>

                {/* Issue Description */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Issue Description</label>
                  <Textarea
                    value={issueDescription}
                    onChange={(e) => setIssueDescription(e.target.value)}
                    placeholder="Describe the issue or improvement you want to fix. Be specific about what needs to be changed."
                    rows={5}
                    disabled={isSubmitting}
                    minLength={10}
                    required
                  />
                  <p className="text-[10px] text-muted-foreground">
                    Minimum 10 characters. Be clear and specific.
                  </p>
                </div>

                {/* Advanced Options Toggle */}
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="w-full justify-between"
                >
                  <span>Advanced Options</span>
                  {showAdvanced ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </Button>

                {showAdvanced && (
                  <Card className="bg-muted/50">
                    <CardContent className="p-4 space-y-4">
                      {/* Model Selection */}
                      <div className="space-y-2">
                        <label className="text-sm font-medium">AI Model</label>
                        <select
                          value={model}
                          onChange={(e) => setModel(e.target.value)}
                          className="w-full h-10 px-3 rounded-md border border-input bg-background text-sm"
                          disabled={isSubmitting}
                        >
                          {MODELS.map((m) => (
                            <option key={m.value} value={m.value}>
                              {m.label} - {m.description}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Temperature */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <label className="text-sm font-medium">Temperature</label>
                          <span className="text-sm text-muted-foreground">{temperature}</span>
                        </div>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.1"
                          value={temperature}
                          onChange={(e) => setTemperature(parseFloat(e.target.value))}
                          className="w-full"
                          disabled={isSubmitting}
                        />
                        <div className="flex justify-between text-[10px] text-muted-foreground">
                          <span>Focused</span>
                          <span>Creative</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Submit Button */}
                <Button
                  type="submit"
                  disabled={!isFormValid || isSubmitting || !isHealthy || currentTaskId}
                  className="w-full"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Submitting...
                    </>
                  ) : (
                    <>
                      <Zap className="h-4 w-4 mr-2" />
                      Generate Fix
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Right: Status or Guide */}
          {currentTaskId || statusData ? (
            <StatusDisplay
              taskId={currentTaskId}
              status={statusData}
              onReset={handleReset}
              onViewPatch={handleViewPatch}
              onDownloadPatch={handleDownloadPatch}
            />
          ) : (
            <HowItWorksGuide isHealthy={isHealthy} />
          )}
        </div>
      </div>

      {/* Patch Modal */}
      {showPatchModal && (
        <PatchModal
          patch={patchContent}
          loading={loadingPatch}
          onClose={() => {
            setShowPatchModal(false);
            setPatchContent(null);
          }}
          taskId={currentTaskId}
        />
      )}
    </>
  );
}
