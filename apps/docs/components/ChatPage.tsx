import { useState, useRef, useEffect, useCallback } from 'react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  citations?: Array<{
    text?: string;
    sources: Array<{ content?: string; location?: string }>;
  }>;
}

interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
}

const SUGGESTED_QUESTIONS = [
  'How do I get started with TraceCraft?',
  'What decorators are available for tracing?',
  'How do I integrate TraceCraft with LangChain?',
  'What exporters does TraceCraft support?',
  'How do I configure redaction for sensitive data?',
  'How do I set up multi-tenancy?',
];

export function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversation, setCurrentConversation] = useState<Conversation | null>(null);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>();
  const [showSidebar, setShowSidebar] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentConversation?.messages]);

  const createNewConversation = useCallback(() => {
    const newConversation: Conversation = {
      id: Date.now().toString(),
      title: 'New conversation',
      messages: [],
      createdAt: new Date(),
    };
    setConversations((prev) => [newConversation, ...prev]);
    setCurrentConversation(newConversation);
    setSessionId(undefined);
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!input.trim() || isLoading) return;

      const userMessage = input.trim();
      setInput('');

      // Create conversation if none exists
      let conversation = currentConversation;
      if (!conversation) {
        conversation = {
          id: Date.now().toString(),
          title: userMessage.slice(0, 50) + (userMessage.length > 50 ? '...' : ''),
          messages: [],
          createdAt: new Date(),
        };
        setConversations((prev) => [conversation!, ...prev]);
        setCurrentConversation(conversation);
      }

      const newUserMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content: userMessage,
        timestamp: new Date(),
      };

      // Update conversation title if it's the first message
      if (conversation.messages.length === 0) {
        conversation = {
          ...conversation,
          title: userMessage.slice(0, 50) + (userMessage.length > 50 ? '...' : ''),
        };
      }

      const updatedConversation = {
        ...conversation,
        messages: [...conversation.messages, newUserMessage],
      };

      setCurrentConversation(updatedConversation);
      setConversations((prev) =>
        prev.map((c) => (c.id === updatedConversation.id ? updatedConversation : c))
      );

      setIsLoading(true);

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: userMessage, sessionId }),
        });

        const data = await res.json();

        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: res.ok ? data.answer : `Error: ${data.error}`,
          timestamp: new Date(),
          citations: res.ok ? data.citations : undefined,
        };

        if (res.ok) {
          setSessionId(data.sessionId);
        }

        const finalConversation = {
          ...updatedConversation,
          messages: [...updatedConversation.messages, assistantMessage],
        };

        setCurrentConversation(finalConversation);
        setConversations((prev) =>
          prev.map((c) => (c.id === finalConversation.id ? finalConversation : c))
        );
      } catch {
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: 'Failed to connect to chat service.',
          timestamp: new Date(),
        };

        const finalConversation = {
          ...updatedConversation,
          messages: [...updatedConversation.messages, errorMessage],
        };

        setCurrentConversation(finalConversation);
        setConversations((prev) =>
          prev.map((c) => (c.id === finalConversation.id ? finalConversation : c))
        );
      } finally {
        setIsLoading(false);
      }
    },
    [input, isLoading, currentConversation, sessionId]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const selectConversation = (conversation: Conversation) => {
    setCurrentConversation(conversation);
    setSessionId(undefined); // Reset session for historical conversations
  };

  const deleteConversation = (id: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (currentConversation?.id === id) {
      setCurrentConversation(null);
      setSessionId(undefined);
    }
  };

  const extractSourceUrl = (location?: string): string | null => {
    if (!location) return null;
    // Extract page path from S3 location
    // e.g., s3://bucket/docs/getting-started/index.md -> /getting-started
    const match = location.match(/docs\/(.+?)(?:\.md|\.mdx)?$/);
    if (match) {
      let path = match[1];
      if (path.endsWith('/index')) {
        path = path.replace(/\/index$/, '');
      }
      return `/${path}`;
    }
    return null;
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] -mx-4 sm:-mx-6 lg:-mx-8">
      {/* Sidebar */}
      {showSidebar && (
        <div className="w-64 border-r dark:border-gray-700 bg-gray-50 dark:bg-gray-900 flex flex-col">
          <div className="p-3 border-b dark:border-gray-700">
            <button
              onClick={createNewConversation}
              className="w-full px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors flex items-center justify-center gap-2"
              aria-label="Start new conversation"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              New conversation
            </button>
          </div>
          <nav className="flex-1 overflow-y-auto" aria-label="Conversation history">
            {conversations.map((conv) => (
              <div
                key={conv.id}
                className={`group flex items-center gap-2 px-3 py-2 ${
                  currentConversation?.id === conv.id
                    ? 'bg-gray-200 dark:bg-gray-800'
                    : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                }`}
              >
                <button
                  onClick={() => selectConversation(conv)}
                  className="flex items-center gap-2 flex-1 text-left"
                  aria-current={currentConversation?.id === conv.id ? 'true' : undefined}
                >
                  <svg
                    className="w-4 h-4 text-gray-400 flex-shrink-0"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                    />
                  </svg>
                  <span className="text-sm truncate flex-1">{conv.title}</span>
                </button>
                <button
                  onClick={() => deleteConversation(conv.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500"
                  aria-label={`Delete conversation: ${conv.title}`}
                >
                  <svg
                    className="w-3 h-3"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>
            ))}
          </nav>
        </div>
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col">
        {/* Toggle sidebar button */}
        <div className="p-2 border-b dark:border-gray-700 flex items-center gap-2">
          <button
            onClick={() => setShowSidebar(!showSidebar)}
            className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 rounded hover:bg-gray-100 dark:hover:bg-gray-800"
            aria-label={showSidebar ? 'Hide sidebar' : 'Show sidebar'}
            aria-expanded={showSidebar}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>
          <h1 className="text-lg font-semibold">TraceCraft AI Assistant</h1>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto p-4">
          {!currentConversation || currentConversation.messages.length === 0 ? (
            <div className="max-w-2xl mx-auto mt-8">
              <div className="text-center mb-8">
                <h2 className="text-2xl font-bold mb-2">Ask about TraceCraft</h2>
                <p className="text-gray-500 dark:text-gray-400">
                  Get answers from the TraceCraft documentation using AI
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {SUGGESTED_QUESTIONS.map((question) => (
                  <button
                    key={question}
                    onClick={() => setInput(question)}
                    className="p-3 text-left text-sm border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 dark:border-gray-700 transition-colors"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-4">
              {currentConversation.messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] p-4 rounded-lg ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 dark:bg-gray-800'
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                        <p className="text-xs font-medium mb-2 opacity-70">Sources:</p>
                        <div className="space-y-1">
                          {msg.citations.flatMap((c, ci) =>
                            c.sources.map((s, si) => {
                              const url = extractSourceUrl(s.location);
                              return url ? (
                                <a
                                  key={`${ci}-${si}`}
                                  href={url}
                                  className="block text-xs text-blue-600 dark:text-blue-400 hover:underline"
                                >
                                  {url}
                                </a>
                              ) : null;
                            })
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg">
                    <span className="inline-flex items-center gap-1">
                      <span className="animate-pulse">Thinking</span>
                      <span className="animate-bounce">.</span>
                      <span className="animate-bounce" style={{ animationDelay: '0.1s' }}>
                        .
                      </span>
                      <span className="animate-bounce" style={{ animationDelay: '0.2s' }}>
                        .
                      </span>
                    </span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input area */}
        <div className="border-t dark:border-gray-700 p-4">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
            <div className="flex gap-2">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a question about TraceCraft..."
                rows={1}
                className="flex-1 px-4 py-3 border rounded-lg resize-none dark:bg-gray-800 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={isLoading}
                aria-label="Question input"
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg disabled:opacity-50 hover:bg-blue-700 transition-colors flex items-center gap-2"
                aria-label="Send message"
              >
                <span>Send</span>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                  />
                </svg>
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-2 text-center">
              AI responses are generated from TraceCraft documentation. Always verify important
              information.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
