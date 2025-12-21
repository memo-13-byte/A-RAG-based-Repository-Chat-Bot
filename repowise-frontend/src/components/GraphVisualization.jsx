/**
 * GraphVisualization - FIXED VERSION
 * Handles both string and object selectedRepository types
 */

import React, { useState, useEffect } from 'react';
import api from '../services/api';

const GraphVisualization = ({ selectedRepository }) => {
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [maxNodes, setMaxNodes] = useState(50);

  const parseRepoUrl = (url) => {
    const match = url.match(/github\.com\/([^\/]+)\/([^\/]+)/);
    return match ? { owner: match[1], repo: match[2] } : null;
  };

  const fetchGraph = async () => {
    if (!selectedRepository) return;

    setLoading(true);
    setError(null);

    try {
      // FIX: Handle both string and object types
      const repoUrl = selectedRepository?.url || selectedRepository;
      const parsed = parseRepoUrl(repoUrl);

      if (!parsed) throw new Error('Invalid repository URL');

      const { owner, repo } = parsed;

      // FIX: Add /api prefix to match backend routes
      const response = await api.get(
        `/api/graph/visualize/${owner}/${repo}?max_nodes=${maxNodes}`
      );

      setGraphData(response.data);
    } catch (err) {
      console.error('Graph fetch error:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to load graph data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();
  }, [selectedRepository, maxNodes]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading graph...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800 font-semibold mb-2">Error loading graph:</p>
          <p className="text-red-600 text-sm">{error}</p>
          <button
            onClick={fetchGraph}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            Retry
          </button>
        </div>
        <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-blue-800 font-semibold mb-2">💡 To use the graph feature:</p>
          <ol className="text-sm text-blue-700 space-y-1 list-decimal list-inside">
            <li>Make sure backend is running</li>
            <li>Analyze the repository first (via Swagger or API)</li>
            <li>Wait for analysis to complete</li>
            <li>Then refresh this page</li>
          </ol>
        </div>
      </div>
    );
  }

  if (!graphData) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-gray-500 p-8">
          <p className="text-lg mb-2">📊 No graph data available</p>
          <p className="text-sm mb-4">Repository needs to be analyzed first</p>
          <div className="text-xs text-gray-600 space-y-1">
            <p>Use the Graph API to analyze:</p>
            <code className="block bg-gray-100 p-2 rounded mt-2">
              POST /api/graph/analyze?repository_url=...
            </code>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 h-full overflow-y-auto">
      {/* Controls Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Code Graph</h2>
          <p className="text-sm text-gray-600">
            {graphData.nodes?.length || 0} nodes, {graphData.edges?.length || 0} edges
          </p>
        </div>

        <div className="flex items-center gap-4">
          <label className="text-sm text-gray-700">
            Max Nodes:
            <input
              type="number"
              value={maxNodes}
              onChange={(e) => setMaxNodes(parseInt(e.target.value))}
              className="ml-2 w-20 px-2 py-1 border rounded"
              min="10"
              max="200"
            />
          </label>
          <button
            onClick={fetchGraph}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            🔄 Refresh
          </button>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
          <p className="text-sm text-gray-600 mb-1">Classes</p>
          <p className="text-3xl font-bold text-blue-600">
            {graphData.statistics?.classes || 0}
          </p>
        </div>
        <div className="bg-green-50 p-4 rounded-lg border border-green-200">
          <p className="text-sm text-gray-600 mb-1">Functions</p>
          <p className="text-3xl font-bold text-green-600">
            {graphData.statistics?.functions || 0}
          </p>
        </div>
        <div className="bg-purple-50 p-4 rounded-lg border border-purple-200">
          <p className="text-sm text-gray-600 mb-1">Files</p>
          <p className="text-3xl font-bold text-purple-600">
            {graphData.statistics?.files || 0}
          </p>
        </div>
        <div className="bg-orange-50 p-4 rounded-lg border border-orange-200">
          <p className="text-sm text-gray-600 mb-1">Relationships</p>
          <p className="text-3xl font-bold text-orange-600">
            {graphData.statistics?.relationships || 0}
          </p>
        </div>
      </div>

      {/* Nodes List */}
      <div className="bg-white rounded-lg border mb-4">
        <div className="p-4 border-b bg-gray-50">
          <h3 className="font-semibold text-gray-800">
            Nodes ({graphData.nodes?.length || 0})
          </h3>
        </div>
        <div className="max-h-96 overflow-y-auto">
          {graphData.nodes?.length > 0 ? (
            graphData.nodes.map((node, idx) => (
              <div
                key={idx}
                className="p-3 border-b hover:bg-gray-50 flex items-center justify-between transition"
              >
                <div>
                  <p className="font-medium text-gray-800">{node.label}</p>
                  {node.file_path && (
                    <p className="text-xs text-gray-500 font-mono">{node.file_path}</p>
                  )}
                </div>
                <span
                  className={`px-3 py-1 rounded text-xs font-medium ${
                    node.type === 'class'
                      ? 'bg-blue-100 text-blue-800'
                      : node.type === 'function'
                      ? 'bg-green-100 text-green-800'
                      : node.type === 'module'
                      ? 'bg-orange-100 text-orange-800'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {node.type}
                </span>
              </div>
            ))
          ) : (
            <div className="p-8 text-center text-gray-500">
              <p>No nodes found</p>
            </div>
          )}
        </div>
      </div>

      {/* Edges List */}
      <div className="bg-white rounded-lg border">
        <div className="p-4 border-b bg-gray-50">
          <h3 className="font-semibold text-gray-800">
            Relationships ({graphData.edges?.length || 0})
          </h3>
        </div>
        <div className="max-h-64 overflow-y-auto">
          {graphData.edges?.length > 0 ? (
            graphData.edges.map((edge, idx) => (
              <div key={idx} className="p-3 border-b hover:bg-gray-50 text-sm">
                <div className="flex items-center">
                  <span className="font-medium text-gray-800">{edge.source}</span>
                  <span className="mx-3 text-gray-400">→</span>
                  <span className="font-medium text-gray-800">{edge.target}</span>
                  <span className="ml-3 px-2 py-1 rounded text-xs bg-gray-100 text-gray-600 font-mono">
                    {edge.type}
                  </span>
                </div>
              </div>
            ))
          ) : (
            <div className="p-8 text-center text-gray-500">
              <p>No relationships found</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default GraphVisualization;