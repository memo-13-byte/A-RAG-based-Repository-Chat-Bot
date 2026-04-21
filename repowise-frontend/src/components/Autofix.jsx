import { useState, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { autofixAPI } from '../services/api';
import { Loader2, CheckCircle, XCircle, Clock, Sparkles, AlertCircle, X, Copy, Download } from 'lucide-react';
import axios from 'axios';

const MODELS = [
  { value: 'gpt-4o-mini-2024-07-18', label: 'GPT-4o Mini (Fast)' },
  { value: 'gpt-4o-2024-08-06', label: 'GPT-4o (Balanced)' },
  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo (Advanced)' },
];

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

  // Auto-fill repo URL when repository is selected
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
        return false;
      }
      return 5000;
    },
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    submitMutation.mutate({
      repoUrl,
      issueDescription,
      model,
      temperature,
    });
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
      // Try to fetch the patch content
      // The patch_path is like: /outputs/task_id/task_id_timestamp/selected_patch.json
      const response = await axios.get(statusData.patch_path);
      setPatchContent(response.data);
    } catch (error) {
      console.error('Error fetching patch:', error);
      // If direct fetch fails, show the path info
      setPatchContent({
        error: 'Could not load patch content',
        path: statusData.patch_path,
        message: 'Patch file is available at the path above. You can access it via Docker container.'
      });
    } finally {
      setLoadingPatch(false);
    }
  };

  const handleDownloadPatch = () => {
    if (!statusData?.patch_path) return;

    // Create download link
    const link = document.createElement('a');
    link.href = statusData.patch_path;
    link.download = `patch_${currentTaskId}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const isHealthy = healthData?.healthy;
  const isSubmitting = submitMutation.isPending;
  const isFormValid = repoUrl.trim() !== '' && issueDescription.trim().length >= 10;

  return (
    <>
      <div className="h-full flex flex-col p-6 overflow-y-auto">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center space-x-3 mb-2">
            <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">AutoFix</h2>
              <p className="text-sm text-gray-600">AI-powered automated code fixing</p>
            </div>
          </div>

          {/* Service Status */}
          {!healthLoading && (
            <div
              className={`mt-4 p-3 rounded-lg border ${
                isHealthy
                  ? 'bg-green-50 border-green-200'
                  : 'bg-red-50 border-red-200'
              }`}
            >
              <div className="flex items-center">
                <div
                  className={`w-2 h-2 rounded-full mr-2 ${
                    isHealthy ? 'bg-green-500' : 'bg-red-500'
                  }`}
                />
                <span
                  className={`text-sm font-medium ${
                    isHealthy ? 'text-green-800' : 'text-red-800'
                  }`}
                >
                  {isHealthy ? 'AutoFix Service Online' : 'AutoFix Service Offline'}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1">
          {/* Left: Form */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Repository URL */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Repository URL *
                </label>
                <input
                  type="url"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  placeholder="https://github.com/user/repo.git"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                  disabled={isSubmitting}
                  required
                />
                <p className="mt-1 text-xs text-gray-500">
                  GitHub repository URL to analyze
                </p>
              </div>

              {/* Issue Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Issue Description *
                </label>
                <textarea
                  value={issueDescription}
                  onChange={(e) => setIssueDescription(e.target.value)}
                  placeholder="Describe the issue or improvement you want to fix. Be specific about what needs to be changed."
                  rows={5}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none transition-all"
                  disabled={isSubmitting}
                  minLength={10}
                  required
                />
                <p className="mt-1 text-xs text-gray-500">
                  Minimum 10 characters. Be clear and specific.
                </p>
              </div>

              {/* Advanced Options */}
              <div>
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="text-sm text-purple-600 hover:text-purple-800 font-medium transition-colors"
                >
                  {showAdvanced ? '− Hide' : '+ Show'} Advanced Options
                </button>
              </div>

              {showAdvanced && (
                <div className="space-y-4 p-4 bg-gray-50 rounded-lg">
                  {/* Model Selection */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      AI Model
                    </label>
                    <select
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                      disabled={isSubmitting}
                    >
                      {MODELS.map((m) => (
                        <option key={m.value} value={m.value}>
                          {m.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Temperature */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Temperature: {temperature}
                    </label>
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
                    <div className="flex justify-between text-xs text-gray-500 mt-1">
                      <span>Focused</span>
                      <span>Creative</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={!isFormValid || isSubmitting || !isHealthy || currentTaskId}
                className={`w-full py-3 px-4 rounded-lg font-medium text-white transition-all flex items-center justify-center space-x-2 ${
                  !isFormValid || isSubmitting || !isHealthy || currentTaskId
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 shadow-lg hover:shadow-xl'
                }`}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Submitting...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    <span>Generate Fix</span>
                  </>
                )}
              </button>
            </form>

            {/* Example Issues */}
            <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <h4 className="text-sm font-medium text-blue-900 mb-2 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1" />
                Example Issues
              </h4>
              <ul className="text-xs text-blue-800 space-y-1">
                <li>• Add type hints to the main() function</li>
                <li>• Fix the bug in user authentication logic</li>
                <li>• Refactor database connection to use pooling</li>
                <li>• Add error handling to API endpoints</li>
              </ul>
            </div>
          </div>

          {/* Right: Status or Guide */}
          <div>
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
      </div>

      {/* Patch Modal */}
      {showPatchModal && (
        <PatchModal
          patchContent={patchContent}
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

// Status Display Component
function StatusDisplay({ taskId, status, onReset, onViewPatch, onDownloadPatch }) {
  const getStatusConfig = () => {
    if (!status) {
      return {
        label: 'Processing',
        icon: Clock,
        color: 'blue',
        description: 'Preparing your fix request...',
      };
    }

    switch (status.status) {
      case 'processing':
        return {
          label: 'Processing',
          icon: Clock,
          color: 'blue',
          description: 'Cloning repository and preparing analysis...',
        };
      case 'running':
        return {
          label: 'Analyzing',
          icon: Loader2,
          color: 'yellow',
          description: 'AI is analyzing the code and generating a fix...',
        };
      case 'completed':
        return {
          label: 'Completed',
          icon: CheckCircle,
          color: 'green',
          description: 'Fix generated successfully!',
        };
      case 'failed':
        return {
          label: 'Failed',
          icon: XCircle,
          color: 'red',
          description: 'Failed to generate fix',
        };
      default:
        return {
          label: 'Unknown',
          icon: AlertCircle,
          color: 'gray',
          description: 'Unknown status',
        };
    }
  };

  const config = getStatusConfig();
  const Icon = config.icon;

  const colorClasses = {
    blue: {
      bg: 'bg-blue-50',
      border: 'border-blue-200',
      text: 'text-blue-800',
      badge: 'bg-blue-100 text-blue-800',
    },
    yellow: {
      bg: 'bg-yellow-50',
      border: 'border-yellow-200',
      text: 'text-yellow-800',
      badge: 'bg-yellow-100 text-yellow-800',
    },
    green: {
      bg: 'bg-green-50',
      border: 'border-green-200',
      text: 'text-green-800',
      badge: 'bg-green-100 text-green-800',
    },
    red: {
      bg: 'bg-red-50',
      border: 'border-red-200',
      text: 'text-red-800',
      badge: 'bg-red-100 text-red-800',
    },
  };

  const colors = colorClasses[config.color];

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-bold text-gray-900">Fix Status</h3>
        {(status?.status === 'completed' || status?.status === 'failed') && (
          <button
            onClick={onReset}
            className="text-sm text-purple-600 hover:text-purple-800 font-medium transition-colors"
          >
            ← Start New Fix
          </button>
        )}
      </div>

      {/* Status Card */}
      <div className={`${colors.bg} border ${colors.border} rounded-lg p-4`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <Icon
              className={`w-6 h-6 ${config.color === 'yellow' || config.color === 'blue' ? 'animate-spin' : ''}`}
            />
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${colors.badge}`}>
              {config.label}
            </span>
          </div>
        </div>

        <p className={`${colors.text} text-sm mb-3`}>{config.description}</p>

        <div className="mt-2">
          <p className="text-xs text-gray-500">
            Task ID: <code className="bg-white px-2 py-1 rounded">{taskId}</code>
          </p>
        </div>

        {/* Error */}
        {status?.status === 'failed' && status?.error && (
          <div className="mt-3 p-3 bg-white rounded border border-red-200">
            <p className="text-sm font-medium text-red-800 mb-1">Error:</p>
            <p className="text-sm text-red-700">{status.error}</p>
          </div>
        )}

        {/* Success - Patch Path */}
        {status?.status === 'completed' && status?.patch_path && (
          <div className="mt-4 space-y-3">
            <div className="p-3 bg-white rounded border border-green-200">
              <p className="text-sm font-medium text-green-800 mb-1">📄 Patch Generated</p>
              <p className="text-xs text-gray-600 font-mono break-all">{status.patch_path}</p>
            </div>

            <div className="flex space-x-2">
              <button
                onClick={onDownloadPatch}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-center space-x-1"
              >
                <Download className="w-4 h-4" />
                <span>Download Patch</span>
              </button>
              <button
                onClick={onViewPatch}
                className="flex-1 bg-white hover:bg-gray-50 text-green-700 border border-green-300 px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-center space-x-1"
              >
                <AlertCircle className="w-4 h-4" />
                <span>View Patch</span>
              </button>
            </div>
          </div>
        )}

        {/* Progress Steps */}
        {(status?.status === 'processing' || status?.status === 'running') && (
          <div className="mt-4 space-y-2">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-green-500 rounded-full" />
              <span className="text-sm text-gray-700">Repository cloned</span>
            </div>
            <div className="flex items-center space-x-2">
              <div
                className={`w-2 h-2 ${
                  status?.status === 'running' ? 'bg-green-500' : 'bg-gray-300'
                } rounded-full`}
              />
              <span className="text-sm text-gray-700">Analyzing code structure</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-gray-300 rounded-full animate-pulse" />
              <span className="text-sm text-gray-700">Generating fix with AI...</span>
            </div>
          </div>
        )}
      </div>

      {/* Estimated Time */}
      {(status?.status === 'processing' || status?.status === 'running') && (
        <div className="mt-4 p-3 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-600">
            ⏱️ Estimated time: 10 seconds to 10 minutes depending on complexity
          </p>
        </div>
      )}
    </div>
  );
}

// Patch Modal Component
function PatchModal({ patchContent, loading, onClose, taskId }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    const textToCopy = JSON.stringify(patchContent, null, 2);
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Patch Preview</h2>
            <p className="text-sm text-gray-500 mt-1">Task ID: {taskId}</p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleCopy}
              className="px-4 py-2 bg-purple-100 hover:bg-purple-200 text-purple-700 rounded-lg text-sm font-medium transition-colors flex items-center space-x-1"
            >
              <Copy className="w-4 h-4" />
              <span>{copied ? 'Copied!' : 'Copy'}</span>
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-purple-600" />
              <span className="ml-3 text-gray-600">Loading patch...</span>
            </div>
          ) : patchContent?.error ? (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-800 font-medium mb-2">{patchContent.error}</p>
              <p className="text-sm text-red-700">{patchContent.message}</p>
              {patchContent.path && (
                <p className="mt-2 text-xs text-gray-600 font-mono">
                  Path: {patchContent.path}
                </p>
              )}
            </div>
          ) : (
            <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm overflow-x-auto">
              <pre className="whitespace-pre-wrap">
                {JSON.stringify(patchContent, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 p-4 flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// How It Works Guide
function HowItWorksGuide({ isHealthy }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <h3 className="text-xl font-bold text-gray-900 mb-4">How It Works</h3>

      <div className="space-y-4">
        <div className="flex items-start">
          <div className="flex-shrink-0 w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center">
            <span className="text-purple-600 font-bold">1</span>
          </div>
          <div className="ml-4">
            <h4 className="font-medium text-gray-900">Submit Repository</h4>
            <p className="text-sm text-gray-600">
              Provide a GitHub repository URL and describe the issue
            </p>
          </div>
        </div>

        <div className="flex items-start">
          <div className="flex-shrink-0 w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center">
            <span className="text-purple-600 font-bold">2</span>
          </div>
          <div className="ml-4">
            <h4 className="font-medium text-gray-900">AI Analysis</h4>
            <p className="text-sm text-gray-600">
              AI analyzes your code and understands the context
            </p>
          </div>
        </div>

        <div className="flex items-start">
          <div className="flex-shrink-0 w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center">
            <span className="text-purple-600 font-bold">3</span>
          </div>
          <div className="ml-4">
            <h4 className="font-medium text-gray-900">Generate Fix</h4>
            <p className="text-sm text-gray-600">
              Receive a ready-to-apply patch file
            </p>
          </div>
        </div>

        <div className="flex items-start">
          <div className="flex-shrink-0 w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center">
            <span className="text-purple-600 font-bold">4</span>
          </div>
          <div className="ml-4">
            <h4 className="font-medium text-gray-900">Review & Apply</h4>
            <p className="text-sm text-gray-600">Review and apply the patch to your code</p>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="mt-6 pt-6 border-t border-gray-200">
        <h4 className="font-medium text-gray-900 mb-3">Success Metrics</h4>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-purple-50 rounded-lg p-3">
            <p className="text-2xl font-bold text-purple-600">10s-10m</p>
            <p className="text-xs text-gray-600">Average Time</p>
          </div>
          <div className="bg-green-50 rounded-lg p-3">
            <p className="text-2xl font-bold text-green-600">High</p>
            <p className="text-xs text-gray-600">Success Rate</p>
          </div>
        </div>
      </div>
    </div>
  );
}
