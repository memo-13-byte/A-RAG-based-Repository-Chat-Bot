import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { repositoryAPI } from '../services/api';
import { Github, Star, Code, Loader2, Search } from 'lucide-react';

export default function RepositorySelector({ onSelectRepository, selectedRepository }) {
    const [searchQuery, setSearchQuery] = useState('');

    // Fetch repositories
    const { data: repositories, isLoading, error } = useQuery({
        queryKey: ['repositories'],
        queryFn: repositoryAPI.listRepositories,
    });

    const filteredRepositories = repositories?.filter(repo =>
        repo.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        repo.description?.toLowerCase().includes(searchQuery.toLowerCase())
    ) || [];

    return (
        <div className="bg-white rounded-lg shadow-lg p-6 h-full overflow-hidden flex flex-col">
            {/* Header */}
            <div className="mb-6">
                <h2 className="text-2xl font-bold text-gray-900 mb-2 flex items-center gap-2">
                    <Github className="w-7 h-7 text-primary-600" />
                    Repositories
                </h2>
                <p className="text-sm text-gray-600">
                    Choose a repository to analyzing
                </p>
            </div>

            {/* Search */}
            <div className="mb-4">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input 
                        type="text"
                        placeholder="Search Repository..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                </div>
            </div>

            {/* Repository List */}
            <div className="flex-1 overflow-y-auto space-y-3">
                {isLoading && (
                    <div className="flex items-center justify-center py-8">
                        <Loader2 className="w-8 h-8 animate-spin text-primary-500" />
                    </div>
                )}

                {error && (
                    <div className="text-center py-8">
                        <p className="text-red-500">Repositories cannot be loaded</p>
                        <p className="text-sm text-gray-500 mt-2">{error.message}</p>
                    </div>
                )}

                {!isLoading && !error && filteredRepositories.length === 0 && (
                    <div className="text-center py-8">
                        <Github className="w-12 h-12 mx-auto text-gray-300 mb-3" />
                        <p className="text-gray-500">Cannot be found any repository</p>
                    </div>
                )}

                {filteredRepositories.map((repo) => (
                    <button
                        key={repo.url}
                        onClick={() => onSelectRepository(repo)}
                        className={`w-full text-left p-4 rounded-lg border-2 transition-all hover:shadow-md ${
                            selectedRepository?.url === repo.url
                            ? 'border-primary-500 bg-primary-50'
                            : 'border-gray-200 hover:border-primary-300'
                        }`}
                    >
                        <div className="flex items-start justify-between">
                            <div className="flex-1">
                                <h3 className="font-semibold text-gray-900 mb-1 flex items-center gap-2">
                                    <Code className="w-4 h-4 text-gray-500" />
                                    {repo.name}
                                </h3>
                                {repo.description && (
                                    <p className="text-sm text-gray-600 mb-2">{repo.description}</p>
                                )}
                                <div className="flex items-center gap-4 text-xs text-gray-500">
                                    {repo.language && (
                                        <span className="flex item-center gap-1">
                                            <span className="w-3 h-3 rounded-full bg-blue-500"></span>
                                            {repo.language}
                                        </span>
                                    )}
                                    {repo.stars !== undefined && (
                                        <span className="flex items-center gap-1">
                                            <Star className="w-3 h-3 fill-yellow-400 text-yellow-400" />
                                            {repo.stars.toLocaleString()}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    </button>
                ))}
            </div>

            {/* Selected Repository Info */}
            {selectedRepository && (
                <div className="mt-4 p-3 bg-primary-50 border border-primary-200 rounded-lg">
                    <p className="text-xs text-primary-700 font-medium mb-1">Selected Repository:</p>
                    <p className="text-sm text-primary-900 font-semibold">{selectedRepository.name}</p>
                </div>
            )}
        </div>
    );
}