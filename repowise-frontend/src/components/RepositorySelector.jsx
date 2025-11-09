import { useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { repositoryAPI } from "../services/api"
import { Github, Search, Loader2, CheckCircle2, AlertCircle } from "lucide-react"

export default function RepositorySelector({ onSelectRepository, selectedRepository }) {
  const [repoUrl, setRepoUrl] = useState("")

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
      refetch()
      if (data.repository) {
        onSelectRepository(data.repository)
      }
    },
  })

  const handleAnalyze = () => {
    if (!repoUrl.trim()) return
    analyzeRepoMutation.mutate(repoUrl)
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
        {analyzeRepoMutation.isError && (
          <p className="mt-2 text-sm text-red-600 flex items-center gap-1">
            <AlertCircle className="w-4 h-4" />
            Failed to analyze repository
          </p>
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
              <button
                key={repo.id}
                onClick={() => onSelectRepository(repo)}
                className={`w-full text-left px-4 py-3 rounded-lg border transition-all ${
                  selectedRepository?.id === repo.id
                    ? "border-primary-500 bg-primary-50"
                    : "border-gray-200 hover:border-primary-300 hover:bg-gray-50"
                }`}
              >
                <div className="flex items-start space-x-3">
                  <Github
                    className={`w-5 h-5 mt-0.5 flex-shrink-0 ${
                      selectedRepository?.id === repo.id ? "text-primary-600" : "text-gray-400"
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <p
                      className={`font-medium text-sm truncate ${
                        selectedRepository?.id === repo.id ? "text-primary-900" : "text-gray-900"
                      }`}
                    >
                      {repo.name}
                    </p>
                    <p className="text-xs text-gray-500 truncate mt-0.5">{repo.url}</p>
                    {repo.analyzed_at && (
                      <p className="text-xs text-gray-400 mt-1">
                        Analyzed: {new Date(repo.analyzed_at).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="text-center py-8">
            <Github className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p className="text-sm text-gray-500">No repositories yet</p>
            <p className="text-xs text-gray-400 mt-1">Add a repository above to get started</p>
          </div>
        )}
      </div>
    </div>
  )
}
