import { useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { repositoryAPI } from "../services/api"
import { Github, Search, Loader2, CheckCircle2, AlertCircle, Network } from "lucide-react"
import api from "../services/api"

export default function RepositorySelector({ onSelectRepository, selectedRepository }) {
  const [repoUrl, setRepoUrl] = useState("")
  const [errorDetails, setErrorDetails] = useState(null)

  // Fetch repositories list
  const {
    data: repositories,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["repositories"],
    queryFn: repositoryAPI.listRepositories,
  })

  // Analyze repository mutation
  const analyzeRepoMutation = useMutation({
    mutationFn: (url) => repositoryAPI.analyzeRepository(url),
    onSuccess: (data) => {
      setRepoUrl("")
      setErrorDetails(null)
      refetch()
      if (data.repository) {
        onSelectRepository(data.repository)
      }
    },
    onError: (error) => {
      console.error('Repository analyze error:', error)
      console.error('Error response:', error.response?.data)

      const errorMsg = error.response?.data?.detail
        || error.message
        || 'Unknown error occurred'

      setErrorDetails({
        message: errorMsg,
        status: error.response?.status,
        url: repoUrl
      })
    }
  })

  // NEW: Graph analyze mutation
  const analyzeGraphMutation = useMutation({
    mutationFn: async (repoUrl) => {
      const response = await api.post('/api/graph/analyze', null, {
        params: { repository_url: repoUrl }
      })
      return response.data
    },
    onSuccess: (data) => {
      console.log('Graph analyzed:', data)
      alert(`✅ Graph analyzed successfully!\n\nClasses: ${data.statistics?.classes || 0}\nFunctions: ${data.statistics?.functions || 0}\nFiles: ${data.statistics?.processed_files || 0}`)
    },
    onError: (error) => {
      console.error('Graph analyze error:', error)
      alert(`❌ Graph analyze failed:\n${error.response?.data?.detail || error.message}`)
    }
  })

  const handleAnalyze = () => {
    if (!repoUrl.trim()) return
    setErrorDetails(null)
    analyzeRepoMutation.mutate(repoUrl)
  }

  const handleGraphAnalyze = (repoUrl) => {
    if (confirm('⚠️ Graph analysis can take 1-2 minutes for large repositories.\n\nContinue?')) {
      analyzeGraphMutation.mutate(repoUrl)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === "Enter") {
      e.preventDefault()
      handleAnalyze()
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-lg p-6 h-full flex flex-col">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-xl font-bold text-gray-900 mb-2">Repository Selector</h2>
        <p className="text-sm text-gray-500">Select or analyze a GitHub repository</p>
      </div>

      {/* Add Repository */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">Add New Repository</label>
        <div className="flex space-x-2">
          <input
            type="text"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="https://github.com/user/repo"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-sm"
            disabled={analyzeRepoMutation.isPending}
          />
          <button
            onClick={handleAnalyze}
            disabled={!repoUrl.trim() || analyzeRepoMutation.isPending}
            className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {analyzeRepoMutation.isPending ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Search className="w-5 h-5" />
            )}
          </button>
        </div>

        {/* Error Display */}
        {analyzeRepoMutation.isError && errorDetails && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm font-semibold text-red-800 flex items-center gap-1 mb-1">
              <AlertCircle className="w-4 h-4" />
              Failed to analyze repository
            </p>
            <p className="text-xs text-red-700 mb-2">
              {errorDetails.message}
            </p>
            {errorDetails.status && (
              <p className="text-xs text-red-600">
                Status Code: {errorDetails.status}
              </p>
            )}
            <div className="mt-2 pt-2 border-t border-red-200">
              <p className="text-xs text-red-600 font-semibold mb-1">💡 Possible solutions:</p>
              <ul className="text-xs text-red-700 space-y-1 list-disc list-inside">
                {errorDetails.status === 404 && (
                  <>
                    <li>Check if repository URL is correct</li>
                    <li>Make sure repository is public</li>
                  </>
                )}
                {errorDetails.message?.includes('rate limit') && (
                  <>
                    <li>GitHub API rate limit exceeded</li>
                    <li>Wait an hour or add GitHub token to backend</li>
                  </>
                )}
                {errorDetails.message?.includes('Network Error') && (
                  <>
                    <li>Backend may not be running</li>
                    <li>Check: http://localhost:8000/docs</li>
                  </>
                )}
                {!errorDetails.status && (
                  <>
                    <li>Make sure backend is running on port 8000</li>
                    <li>Check browser console for details</li>
                  </>
                )}
              </ul>
            </div>
          </div>
        )}

        {analyzeRepoMutation.isSuccess && (
          <p className="mt-2 text-sm text-green-600 flex items-center gap-1">
            <CheckCircle2 className="w-4 h-4" />
            Repository analyzed successfully
          </p>
        )}
      </div>

      {/* Repository List */}
      <div className="flex-1 overflow-y-auto">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Your Repositories</h3>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          </div>
        ) : repositories && repositories.length > 0 ? (
          <div className="space-y-2">
            {repositories.map((repo) => (
              <div
                key={repo.id}
                className={`rounded-lg border-2 transition-all ${
                  selectedRepository?.id === repo.id
                    ? "border-primary-500 bg-primary-50"
                    : "border-gray-200"
                }`}
              >
                <button
                  onClick={() => onSelectRepository(repo)}
                  className="w-full text-left px-4 py-3 hover:bg-gray-50"
                >
                  <div className="flex items-start gap-3">
                    <Github className="w-5 h-5 mt-0.5 text-gray-600" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 truncate">{repo.full_name}</p>
                      {repo.description && (
                        <p className="text-sm text-gray-600 truncate mt-1">{repo.description}</p>
                      )}
                      <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                          {repo.language || "Unknown"}
                        </span>
                        <span>⭐ {repo.stars?.toLocaleString() || 0}</span>
                      </div>
                    </div>
                  </div>
                </button>

                {/* NEW: Graph Analyze Button */}
                <div className="px-4 pb-3 border-t border-gray-200 pt-2">
                  <button
                    onClick={() => handleGraphAnalyze(repo.url)}
                    disabled={analyzeGraphMutation.isPending}
                    className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {analyzeGraphMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Analyzing Graph...</span>
                      </>
                    ) : (
                      <>
                        <Network className="w-4 h-4" />
                        <span>Analyze Code Graph</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <Github className="w-12 h-12 mx-auto text-gray-300 mb-3" />
            <p className="text-gray-500 text-sm mb-1">No repositories yet</p>
            <p className="text-gray-400 text-xs">Add a repository above to get started</p>
          </div>
        )}
      </div>
    </div>
  )
}