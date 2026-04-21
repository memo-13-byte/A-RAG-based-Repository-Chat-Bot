import { useState, useEffect, useCallback, useMemo } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Panel,
} from 'reactflow';
import 'reactflow/dist/style.css';
import api from '../services/api';
import { cn } from '../lib/utils';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { ScrollArea } from './ui/scroll-area';
import { Skeleton } from './ui/skeleton';
import {
  RefreshCw,
  Search,
  Network,
  Box,
  FunctionSquare,
  File,
  AlertCircle,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Filter,
  X,
  ChevronRight,
} from 'lucide-react';

// Node type colors
const nodeColors = {
  class: { bg: 'bg-blue-500', border: 'border-blue-600', text: 'text-blue-100' },
  function: { bg: 'bg-emerald-500', border: 'border-emerald-600', text: 'text-emerald-100' },
  module: { bg: 'bg-amber-500', border: 'border-amber-600', text: 'text-amber-100' },
  file: { bg: 'bg-violet-500', border: 'border-violet-600', text: 'text-violet-100' },
  default: { bg: 'bg-slate-500', border: 'border-slate-600', text: 'text-slate-100' },
};

// Custom Node Component
function CustomNode({ data }) {
  const colors = nodeColors[data.type] || nodeColors.default;
  const Icon = data.type === 'class' ? Box : data.type === 'function' ? FunctionSquare : File;

  return (
    <div
      className={cn(
        "px-3 py-2 rounded-lg shadow-lg border-2 min-w-[120px] transition-all",
        colors.bg, colors.border,
        "hover:scale-105 hover:shadow-xl"
      )}
    >
      <div className="flex items-center gap-2">
        <Icon className={cn("h-4 w-4", colors.text)} />
        <span className={cn("text-sm font-medium truncate max-w-[150px]", colors.text)}>
          {data.label}
        </span>
      </div>
      {data.file_path && (
        <p className="text-[10px] opacity-70 mt-1 truncate max-w-[150px]" title={data.file_path}>
          {data.file_path.split('/').pop()}
        </p>
      )}
    </div>
  );
}

const nodeTypes = { custom: CustomNode };

// Stats Card Component
function StatsCard({ label, value, icon: Icon, color }) {
  return (
    <div className={cn("p-3 rounded-lg border", color)}>
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{label}</span>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  );
}

// Node List Panel
function NodeListPanel({ nodes, onNodeClick, filter, setFilter }) {
  const filteredNodes = useMemo(() => {
    if (!filter) return nodes;
    return nodes.filter(node => 
      node.data.label.toLowerCase().includes(filter.toLowerCase()) ||
      node.data.type.toLowerCase().includes(filter.toLowerCase())
    );
  }, [nodes, filter]);

  return (
    <Card className="w-72 h-full flex flex-col">
      <CardHeader className="p-3 pb-2">
        <CardTitle className="text-sm font-medium flex items-center justify-between">
          Nodes ({filteredNodes.length})
          {filter && (
            <Button variant="ghost" size="icon" className="h-5 w-5" onClick={() => setFilter('')}>
              <X className="h-3 w-3" />
            </Button>
          )}
        </CardTitle>
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter nodes..."
            className="h-8 pl-8 text-xs"
          />
        </div>
      </CardHeader>
      <CardContent className="p-0 flex-1 min-h-0">
        <ScrollArea className="h-full px-3 pb-3">
          <div className="space-y-1">
            {filteredNodes.map((node) => {
              const colors = nodeColors[node.data.type] || nodeColors.default;
              const Icon = node.data.type === 'class' ? Box : node.data.type === 'function' ? FunctionSquare : File;
              return (
                <button
                  key={node.id}
                  onClick={() => onNodeClick(node)}
                  className="w-full text-left p-2 rounded-md hover:bg-accent transition-colors flex items-center gap-2 group"
                >
                  <div className={cn("p-1 rounded", colors.bg)}>
                    <Icon className={cn("h-3 w-3", colors.text)} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{node.data.label}</p>
                    <p className="text-[10px] text-muted-foreground truncate">
                      {node.data.file_path || node.data.type}
                    </p>
                  </div>
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100" />
                </button>
              );
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

// Empty/Loading States
function EmptyState({ message, description }) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
          <Network className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold mb-2">{message}</h3>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center">
        <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4 animate-pulse">
          <Network className="h-8 w-8 text-primary" />
        </div>
        <h3 className="text-lg font-semibold mb-2">Loading Graph</h3>
        <p className="text-sm text-muted-foreground">Fetching code structure data...</p>
      </div>
    </div>
  );
}

function ErrorState({ error, onRetry }) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 rounded-2xl bg-destructive/10 flex items-center justify-center mx-auto mb-4">
          <AlertCircle className="h-8 w-8 text-destructive" />
        </div>
        <h3 className="text-lg font-semibold mb-2">Failed to Load Graph</h3>
        <p className="text-sm text-muted-foreground mb-4">{error}</p>
        <Button onClick={onRetry} variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Try Again
        </Button>
        <Card className="mt-6 text-left">
          <CardContent className="p-4">
            <p className="text-xs font-semibold text-muted-foreground mb-2">To use the graph feature:</p>
            <ol className="text-xs text-muted-foreground space-y-1 list-decimal list-inside">
              <li>Ensure the backend is running</li>
              <li>Analyze the repository first</li>
              <li>Wait for analysis to complete</li>
              <li>Refresh this page</li>
            </ol>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// Main Component
export default function GraphVisualization({ selectedRepository }) {
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [maxNodes, setMaxNodes] = useState(50);
  const [showNodeList, setShowNodeList] = useState(true);
  const [nodeFilter, setNodeFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const parseRepoUrl = (url) => {
    const match = url.match(/github\.com\/([^\/]+)\/([^\/]+)/);
    return match ? { owner: match[1], repo: match[2] } : null;
  };

  const fetchGraph = useCallback(async () => {
    if (!selectedRepository) return;

    setLoading(true);
    setError(null);

    try {
      const repoUrl = selectedRepository?.url || selectedRepository;
      const parsed = parseRepoUrl(repoUrl);

      if (!parsed) throw new Error('Invalid repository URL');

      const { owner, repo } = parsed;

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
  }, [selectedRepository, maxNodes]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  // Transform graph data to ReactFlow format
  useEffect(() => {
    if (!graphData?.nodes) return;

    // Filter nodes by type
    const filteredData = typeFilter === 'all' 
      ? graphData.nodes 
      : graphData.nodes.filter(n => n.type === typeFilter);

    // Create positions using a simple layout algorithm
    const nodeCount = filteredData.length;
    const cols = Math.ceil(Math.sqrt(nodeCount));
    const spacing = 200;

    const flowNodes = filteredData.map((node, index) => ({
      id: node.id || node.label,
      type: 'custom',
      position: {
        x: (index % cols) * spacing + Math.random() * 50,
        y: Math.floor(index / cols) * spacing + Math.random() * 50,
      },
      data: {
        label: node.label,
        type: node.type,
        file_path: node.file_path,
      },
    }));

    const flowEdges = (graphData.edges || [])
      .filter(edge => {
        const sourceExists = flowNodes.some(n => n.id === edge.source);
        const targetExists = flowNodes.some(n => n.id === edge.target);
        return sourceExists && targetExists;
      })
      .map((edge, index) => ({
        id: `edge-${index}`,
        source: edge.source,
        target: edge.target,
        label: edge.type,
        animated: edge.type === 'calls' || edge.type === 'imports',
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#6b7280',
        },
        style: { stroke: '#6b7280', strokeWidth: 1.5 },
        labelStyle: { fontSize: 10, fill: '#9ca3af' },
      }));

    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [graphData, typeFilter, setNodes, setEdges]);

  const handleNodeClick = (node) => {
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        selected: n.id === node.id,
      }))
    );
  };

  if (!selectedRepository) {
    return (
      <EmptyState 
        message="No Repository Selected" 
        description="Select a repository from the sidebar to view its code graph"
      />
    );
  }

  if (loading) {
    return <LoadingState />;
  }

  if (error) {
    return <ErrorState error={error} onRetry={fetchGraph} />;
  }

  if (!graphData) {
    return (
      <EmptyState 
        message="No Graph Data" 
        description="The repository needs to be analyzed first. Use the Graph API to analyze the repository structure."
      />
    );
  }

  return (
    <div className="flex h-full">
      {/* Node List Panel */}
      {showNodeList && (
        <div className="border-r border-border">
          <NodeListPanel
            nodes={nodes}
            onNodeClick={handleNodeClick}
            filter={nodeFilter}
            setFilter={setNodeFilter}
          />
        </div>
      )}

      {/* Main Graph Area */}
      <div className="flex-1 flex flex-col min-h-0">
        {/* Stats Bar */}
        <div className="p-4 border-b border-border bg-card/30">
          <div className="grid grid-cols-4 gap-3">
            <StatsCard
              label="Classes"
              value={graphData.statistics?.classes || 0}
              icon={Box}
              color="bg-blue-500/10 border-blue-500/20"
            />
            <StatsCard
              label="Functions"
              value={graphData.statistics?.functions || 0}
              icon={FunctionSquare}
              color="bg-emerald-500/10 border-emerald-500/20"
            />
            <StatsCard
              label="Files"
              value={graphData.statistics?.files || 0}
              icon={File}
              color="bg-violet-500/10 border-violet-500/20"
            />
            <StatsCard
              label="Relationships"
              value={graphData.statistics?.relationships || 0}
              icon={Network}
              color="bg-amber-500/10 border-amber-500/20"
            />
          </div>
        </div>

        {/* ReactFlow Graph */}
        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            attributionPosition="bottom-left"
            className="bg-background"
          >
            <Background color="#e5e7eb" gap={16} />
            <Controls showInteractive={false} />
            <MiniMap
              nodeColor={(node) => {
                const type = node.data?.type || 'default';
                const colors = {
                  class: '#3b82f6',
                  function: '#10b981',
                  module: '#f59e0b',
                  file: '#8b5cf6',
                  default: '#64748b',
                };
                return colors[type];
              }}
              maskColor="rgba(0, 0, 0, 0.1)"
              className="bg-card border border-border rounded-lg"
            />

            {/* Control Panel */}
            <Panel position="top-right" className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowNodeList(!showNodeList)}
                className="bg-background"
              >
                <Filter className="h-4 w-4 mr-1" />
                {showNodeList ? 'Hide' : 'Show'} List
              </Button>

              <div className="flex items-center gap-2 bg-background border border-border rounded-md px-2">
                <span className="text-xs text-muted-foreground">Max:</span>
                <Input
                  type="number"
                  value={maxNodes}
                  onChange={(e) => setMaxNodes(parseInt(e.target.value) || 50)}
                  className="w-16 h-7 text-xs border-0 p-1"
                  min={10}
                  max={200}
                />
              </div>

              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="h-8 px-2 text-xs border border-border rounded-md bg-background"
              >
                <option value="all">All Types</option>
                <option value="class">Classes</option>
                <option value="function">Functions</option>
                <option value="module">Modules</option>
                <option value="file">Files</option>
              </select>

              <Button
                variant="outline"
                size="sm"
                onClick={fetchGraph}
                className="bg-background"
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
            </Panel>

            {/* Legend */}
            <Panel position="bottom-right" className="bg-card border border-border rounded-lg p-3">
              <p className="text-xs font-semibold mb-2">Legend</p>
              <div className="space-y-1">
                {[
                  { type: 'class', label: 'Class', color: 'bg-blue-500' },
                  { type: 'function', label: 'Function', color: 'bg-emerald-500' },
                  { type: 'module', label: 'Module', color: 'bg-amber-500' },
                  { type: 'file', label: 'File', color: 'bg-violet-500' },
                ].map((item) => (
                  <div key={item.type} className="flex items-center gap-2 text-xs">
                    <div className={cn("w-3 h-3 rounded", item.color)} />
                    <span>{item.label}</span>
                  </div>
                ))}
              </div>
            </Panel>
          </ReactFlow>
        </div>
      </div>
    </div>
  );
}
