import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { toast } from 'sonner';
import { chatAPI } from '../services/api';
import { useThemeStore } from '../stores/theme-store';
import { cn } from '../lib/utils';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Switch } from './ui/switch';
import { Card } from './ui/card';
import { ScrollArea } from './ui/scroll-area';
import { Skeleton } from './ui/skeleton';
import {
  Send,
  Copy,
  Check,
  StopCircle,
  Settings2,
  ChevronDown,
  ChevronUp,
  Zap,
  Network,
  BookOpen,
  FileText,
  MessageSquare,
  Sparkles,
  Radio,
  Database,
  RefreshCw,
} from 'lucide-react';

// Code Block Component with Copy Button
function CodeBlock({ language, children }) {
  const [copied, setCopied] = useState(false);
  const { theme } = useThemeStore();
  const isDark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  const handleCopy = () => {
    navigator.clipboard.writeText(String(children));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group my-3">
      <div className="absolute right-2 top-2 z-10">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity bg-background/80 hover:bg-background"
          onClick={handleCopy}
        >
          {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
        </Button>
      </div>
      {language && (
        <div className="absolute left-3 top-2 text-[10px] text-muted-foreground font-mono uppercase">
          {language}
        </div>
      )}
      <SyntaxHighlighter
        language={language || 'text'}
        style={isDark ? oneDark : oneLight}
        customStyle={{
          margin: 0,
          borderRadius: '0.5rem',
          fontSize: '0.8125rem',
          paddingTop: language ? '2rem' : '1rem',
        }}
        showLineNumbers={String(children).split('\n').length > 3}
      >
        {String(children).replace(/\n$/, '')}
      </SyntaxHighlighter>
    </div>
  );
}

// Message Component
function Message({ message, isStreaming }) {
  const isUser = message.role === 'user';
  const isError = message.role === 'error';

  return (
    <div className={cn(
      "flex gap-3 animate-fade-in",
      isUser ? "justify-end" : "justify-start"
    )}>
      {!isUser && (
        <div className={cn(
          "w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1",
          isError ? "bg-destructive/10" : "bg-primary/10"
        )}>
          {isError ? (
            <span className="text-destructive text-sm">!</span>
          ) : (
            <Sparkles className="h-4 w-4 text-primary" />
          )}
        </div>
      )}
      
      <div className={cn(
        "max-w-[80%] rounded-2xl px-4 py-3",
        isUser && "bg-primary text-primary-foreground",
        !isUser && !isError && "bg-muted",
        isError && "bg-destructive/10 text-destructive border border-destructive/20"
      )}>
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="markdown-content text-sm">
            <ReactMarkdown
              components={{
                code({ inline, className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '');
                  return !inline && match ? (
                    <CodeBlock language={match[1]}>{children}</CodeBlock>
                  ) : (
                    <code className="bg-background/50 dark:bg-background/30 px-1.5 py-0.5 rounded text-[13px] font-mono" {...props}>
                      {children}
                    </code>
                  );
                },
                pre({ children }) {
                  return <>{children}</>;
                },
                p({ children }) {
                  return <p className="mb-2 last:mb-0">{children}</p>;
                },
                ul({ children }) {
                  return <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>;
                },
                ol({ children }) {
                  return <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>;
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
            
            {isStreaming && (
              <span className="inline-block w-2 h-4 bg-foreground/70 ml-0.5 animate-pulse" />
            )}
          </div>
        )}

        {/* Metadata Badges */}
        {!isUser && !isError && message.content && !isStreaming && (
          <div className="flex flex-wrap gap-1.5 mt-3 pt-3 border-t border-border/50">
            {message.streamed && (
              <Badge variant="stream" className="text-[10px]">
                <Radio className="h-2.5 w-2.5 mr-1" />
                Streamed
              </Badge>
            )}
            {message.graph_used && (
              <Badge variant="graph" className="text-[10px]">
                <Network className="h-2.5 w-2.5 mr-1" />
                Graph
              </Badge>
            )}
            {message.rag_used && !message.graph_used && (
              <Badge variant="vector" className="text-[10px]">
                <Database className="h-2.5 w-2.5 mr-1" />
                Vector
              </Badge>
            )}
            {message.rag_used && message.graph_used && (
              <Badge variant="hybrid" className="text-[10px]">
                <Zap className="h-2.5 w-2.5 mr-1" />
                Hybrid
              </Badge>
            )}
            {message.confidence > 0 && (
              <Badge 
                variant={message.confidence >= 0.8 ? "success" : message.confidence >= 0.6 ? "warning" : "destructive"}
                className="text-[10px]"
              >
                {(message.confidence * 100).toFixed(0)}%
              </Badge>
            )}
          </div>
        )}

        {/* Sources */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border/50">
            <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">Sources</p>
            <div className="space-y-1">
              {message.sources.slice(0, 3).map((source, idx) => (
                <div key={idx} className="flex items-center gap-1.5 text-xs text-muted-foreground truncate">
                  <FileText className="h-3 w-3 shrink-0" />
                  <span className="truncate font-mono">{source}</span>
                </div>
              ))}
              {message.sources.length > 3 && (
                <p className="text-[10px] text-muted-foreground">+{message.sources.length - 3} more</p>
              )}
            </div>
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center shrink-0 mt-1">
          <span className="text-primary-foreground text-sm font-medium">U</span>
        </div>
      )}
    </div>
  );
}

// Search Mode Selector
function SearchModeSelector({ searchMode, setSearchMode, showAdvanced, setShowAdvanced }) {
  return (
    <div className="space-y-2">
      <button
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="flex items-center justify-between w-full text-xs font-medium text-muted-foreground hover:text-foreground transition"
      >
        <span>Search Mode</span>
        {showAdvanced ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>

      {showAdvanced && (
        <div className="space-y-1 pl-2 border-l-2 border-border">
          {[
            { value: 'auto', label: 'Auto', icon: Zap, description: 'Smart routing based on question' },
            { value: 'graph', label: 'Graph', icon: Network, description: 'Code structure & relationships' },
            { value: 'vector', label: 'Vector', icon: Database, description: 'Semantic code search' },
          ].map((mode) => {
            const Icon = mode.icon;
            return (
              <label
                key={mode.value}
                className={cn(
                  "flex items-start gap-2 p-2 rounded-lg cursor-pointer transition",
                  searchMode === mode.value ? "bg-accent" : "hover:bg-accent/50"
                )}
              >
                <input
                  type="radio"
                  value={mode.value}
                  checked={searchMode === mode.value}
                  onChange={(e) => setSearchMode(e.target.value)}
                  className="mt-1 h-3.5 w-3.5"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-1.5 text-sm font-medium">
                    <Icon className="h-3.5 w-3.5" />
                    {mode.label}
                  </div>
                  <p className="text-[10px] text-muted-foreground">{mode.description}</p>
                </div>
                {searchMode === mode.value && (
                  <Badge variant="secondary" className="text-[10px]">Active</Badge>
                )}
              </label>
            );
          })}
        </div>
      )}

      {!showAdvanced && (
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span>Current:</span>
          <Badge variant="outline" className="text-[10px]">
            {searchMode === 'auto' && <><Zap className="h-2.5 w-2.5 mr-1" />Auto</>}
            {searchMode === 'graph' && <><Network className="h-2.5 w-2.5 mr-1" />Graph</>}
            {searchMode === 'vector' && <><Database className="h-2.5 w-2.5 mr-1" />Vector</>}
          </Badge>
        </div>
      )}
    </div>
  );
}

// Empty State
function EmptyState({ streamingEnabled }) {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
          <MessageSquare className="h-8 w-8 text-primary" />
        </div>
        <h3 className="text-lg font-semibold mb-2">Start a Conversation</h3>
        <p className="text-sm text-muted-foreground mb-6">
          Ask questions about the repository code, structure, or history.
        </p>
        <div className="grid grid-cols-2 gap-2 text-left">
          {[
            { icon: Network, text: 'Who are the main contributors?' },
            { icon: BookOpen, text: 'How does the auth system work?' },
            { icon: FileText, text: 'What changed in the last commit?' },
            { icon: Zap, text: 'Show me the hot spots' },
          ].map((item, idx) => (
            <div key={idx} className="flex items-start gap-2 p-2 rounded-lg bg-muted/50 text-xs">
              <item.icon className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" />
              <span>{item.text}</span>
            </div>
          ))}
        </div>
        {streamingEnabled && (
          <p className="mt-4 text-xs text-primary flex items-center justify-center gap-1.5">
            <Radio className="h-3 w-3" />
            Streaming enabled - responses appear in real-time
          </p>
        )}
      </div>
    </div>
  );
}

// Main Component
export default function ChatWindow({ selectedRepository }) {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [conversationId, setConversationId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [indexStatus, setIndexStatus] = useState(null);
  const [isIndexing, setIsIndexing] = useState(false);

  // Settings
  const [ragEnabled, setRagEnabled] = useState(true);
  const [autoIndex, setAutoIndex] = useState(true);
  const [searchMode, setSearchMode] = useState('auto');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // Streaming
  const [streamingEnabled, setStreamingEnabled] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState('');
  const abortControllerRef = useRef(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessage]);

  useEffect(() => {
    if (selectedRepository) {
      checkIndexStatus();
    }
  }, [selectedRepository]);

  const checkIndexStatus = async () => {
    if (!selectedRepository) return;
    try {
      const status = await chatAPI.getIndexStatus(selectedRepository.url);
      setIndexStatus(status);
    } catch (error) {
      console.error('Error checking index status:', error);
      setIndexStatus(null);
    }
  };

  const handleManualIndex = async () => {
    if (!selectedRepository || isIndexing) return;
    setIsIndexing(true);
    try {
      const result = await chatAPI.indexRepository(selectedRepository.url, true, 50);
      await checkIndexStatus();
      toast.success(`Indexed ${result.document_count || 0} chunks successfully`);
    } catch (error) {
      console.error('Error indexing repository:', error);
      toast.error('Failed to index repository');
    } finally {
      setIsIndexing(false);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    setLoading(true);

    setMessages((prev) => [
      ...prev,
      { role: 'user', content: userMessage, timestamp: new Date().toISOString() },
    ]);

    try {
      const useGraph = searchMode !== 'vector';

      if (streamingEnabled) {
        await handleStreamingResponse(userMessage, useGraph);
      } else {
        await handleNormalResponse(userMessage, useGraph);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages((prev) => [
        ...prev,
        {
          role: 'error',
          content: 'Failed to get response. Please try again.',
          timestamp: new Date().toISOString(),
        },
      ]);
      toast.error('Failed to send message');
    } finally {
      setLoading(false);
      setIsStreaming(false);
      setStreamingMessage('');
    }
  };

  const handleStreamingResponse = async (userMessage, useGraph) => {
    setIsStreaming(true);
    setStreamingMessage('');

    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch('/api/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          repository_url: selectedRepository.url,
          conversation_id: conversationId,
          use_llm: true,
          use_rag: ragEnabled,
          auto_index: autoIndex,
          use_graph: useGraph,
          stream: true,
        }),
        signal: abortControllerRef.current.signal,
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let fullMessage = '';
      let metadata = {};

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'start' && !conversationId) {
                setConversationId(data.conversation_id);
              } else if (data.type === 'sources') {
                metadata.sources = data.sources;
              } else if (data.type === 'chunk') {
                fullMessage += data.content;
                setStreamingMessage(fullMessage);
              } else if (data.type === 'done') {
                setMessages((prev) => [
                  ...prev,
                  {
                    role: 'assistant',
                    content: fullMessage,
                    sources: metadata.sources || [],
                    confidence: 0.9,
                    rag_used: ragEnabled,
                    graph_used: useGraph,
                    timestamp: new Date().toISOString(),
                    streamed: true,
                  },
                ]);
                setStreamingMessage('');
              } else if (data.type === 'error') {
                throw new Error(data.message);
              }
            } catch (parseError) {
              console.error('Error parsing SSE data:', parseError);
            }
          }
        }
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: streamingMessage + '\n\n*[Response interrupted]*',
            timestamp: new Date().toISOString(),
            streamed: true,
            interrupted: true,
          },
        ]);
      } else {
        throw error;
      }
    }
  };

  const handleNormalResponse = async (userMessage, useGraph) => {
    const response = await chatAPI.sendMessage(
      userMessage,
      selectedRepository.url,
      conversationId,
      ragEnabled,
      autoIndex,
      useGraph
    );

    if (!conversationId) {
      setConversationId(response.conversation_id);
    }

    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        content: response.message,
        sources: response.sources || [],
        confidence: response.confidence || 0,
        rag_used: response.rag_used || false,
        indexed_chunks: response.indexed_chunks || null,
        graph_used: response.graph_used || false,
        graph_context: response.graph_context || null,
        timestamp: new Date().toISOString(),
        streamed: false,
      },
    ]);

    if (response.indexed_chunks > 0) {
      await checkIndexStatus();
    }
  };

  const handleAbortStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  if (!selectedRepository) {
    return (
      <div className="h-full flex items-center justify-center p-8">
        <div className="text-center">
          <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
            <MessageSquare className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold mb-2">No Repository Selected</h3>
          <p className="text-sm text-muted-foreground">
            Select a repository from the sidebar to start chatting
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Settings Bar */}
      <div className="border-b border-border bg-card/30 px-4 py-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Index Status */}
            {indexStatus ? (
              indexStatus.indexed ? (
                <Badge variant="success" className="text-xs">
                  <Check className="h-3 w-3 mr-1" />
                  Indexed ({indexStatus.total_chunks} chunks)
                </Badge>
              ) : (
                <Badge variant="warning" className="text-xs">
                  Not indexed
                </Badge>
              )
            ) : (
              <Skeleton className="h-5 w-24" />
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={handleManualIndex}
              disabled={isIndexing || (indexStatus && indexStatus.indexed)}
              className="h-7 text-xs"
            >
              {isIndexing ? (
                <>
                  <RefreshCw className="h-3 w-3 animate-spin mr-1" />
                  Indexing...
                </>
              ) : (
                <>
                  <Database className="h-3 w-3 mr-1" />
                  Index Now
                </>
              )}
            </Button>
          </div>

          <div className="flex items-center gap-4">
            {/* Streaming Toggle */}
            <label className="flex items-center gap-2 cursor-pointer">
              <Switch
                checked={streamingEnabled}
                onCheckedChange={setStreamingEnabled}
              />
              <span className="text-xs text-muted-foreground">Stream</span>
            </label>

            {/* RAG Toggle */}
            <label className="flex items-center gap-2 cursor-pointer">
              <Switch checked={ragEnabled} onCheckedChange={setRagEnabled} />
              <span className="text-xs text-muted-foreground">RAG</span>
            </label>

            {/* Settings Button */}
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => setShowSettings(!showSettings)}
            >
              <Settings2 className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Advanced Settings Panel */}
        {showSettings && (
          <div className="mt-3 pt-3 border-t border-border">
            <div className="grid grid-cols-2 gap-4">
              <SearchModeSelector
                searchMode={searchMode}
                setSearchMode={setSearchMode}
                showAdvanced={showAdvanced}
                setShowAdvanced={setShowAdvanced}
              />
              <div className="space-y-2">
                <label className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Auto-Index</span>
                  <Switch checked={autoIndex} onCheckedChange={setAutoIndex} />
                </label>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Messages Area */}
      <ScrollArea className="flex-1 p-4">
        {messages.length === 0 && !isStreaming ? (
          <EmptyState streamingEnabled={streamingEnabled} />
        ) : (
          <div className="space-y-4 max-w-3xl mx-auto">
            {messages.map((message, index) => (
              <Message key={index} message={message} isStreaming={false} />
            ))}

            {/* Streaming Message */}
            {isStreaming && streamingMessage && (
              <Message
                message={{ role: 'assistant', content: streamingMessage }}
                isStreaming={true}
              />
            )}

            {/* Loading Indicator */}
            {loading && !isStreaming && (
              <div className="flex gap-3 justify-start">
                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                  <Sparkles className="h-4 w-4 text-primary animate-pulse" />
                </div>
                <div className="bg-muted rounded-2xl px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-foreground/30 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-foreground/30 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2 h-2 bg-foreground/30 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                    <span className="text-xs text-muted-foreground">Thinking...</span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </ScrollArea>

      {/* Streaming Stop Button */}
      {isStreaming && (
        <div className="flex justify-center pb-2">
          <Button
            variant="destructive"
            size="sm"
            onClick={handleAbortStreaming}
            className="h-7"
          >
            <StopCircle className="h-3.5 w-3.5 mr-1" />
            Stop generating
          </Button>
        </div>
      )}

      {/* Input Area */}
      <div className="border-t border-border bg-card/30 p-4">
        <div className="flex gap-2 max-w-3xl mx-auto">
          <Input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
            placeholder="Ask anything about this repository..."
            disabled={loading}
            className="flex-1"
          />
          <Button
            onClick={handleSendMessage}
            disabled={loading || !inputMessage.trim()}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex items-center justify-center gap-2 mt-2 text-[10px] text-muted-foreground">
          <Badge variant="outline" className="text-[10px]">
            {searchMode === 'auto' && 'Auto'}
            {searchMode === 'graph' && 'Graph'}
            {searchMode === 'vector' && 'Vector'}
          </Badge>
          {streamingEnabled && (
            <span className="flex items-center gap-1">
              <Radio className="h-2.5 w-2.5" />
              Streaming
            </span>
          )}
          {ragEnabled && <span>RAG enabled</span>}
        </div>
      </div>
    </div>
  );
}
