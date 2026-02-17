import { useState, useRef, useEffect, useCallback } from 'react';
import Link from 'next/link';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Array<{
    text?: string;
    sources: Array<{ content?: string; location?: string }>;
  }>;
}

// Generate unique IDs for messages
let messageIdCounter = 0;
function generateMessageId(): string {
  return `msg-${Date.now()}-${++messageIdCounter}`;
}

export function DocsChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>();
  const [error, setError] = useState<string>();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Handle Escape key to close chat
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!input.trim() || isLoading) return;

      const userMessage = input.trim();
      setInput('');
      setError(undefined);
      setMessages((prev) => [
        ...prev,
        { id: generateMessageId(), role: 'user', content: userMessage },
      ]);
      setIsLoading(true);

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: userMessage, sessionId }),
        });

        const data = await res.json();

        if (res.ok) {
          setSessionId(data.sessionId);
          setMessages((prev) => [
            ...prev,
            {
              id: generateMessageId(),
              role: 'assistant',
              content: data.answer,
              citations: data.citations,
            },
          ]);
        } else {
          setError(data.error || 'Something went wrong');
          setMessages((prev) => [
            ...prev,
            {
              id: generateMessageId(),
              role: 'assistant',
              content: `Error: ${data.error}`,
            },
          ]);
        }
      } catch {
        setError('Failed to connect to chat service');
        setMessages((prev) => [
          ...prev,
          {
            id: generateMessageId(),
            role: 'assistant',
            content: 'Failed to connect to chat service.',
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [input, isLoading, sessionId]
  );

  const handleClear = useCallback(() => {
    setMessages([]);
    setSessionId(undefined);
    setError(undefined);
  }, []);

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 bg-blue-600 text-white p-4 rounded-full shadow-lg hover:bg-blue-700 transition-colors z-50 flex items-center gap-2"
        aria-label="Open chat"
        title="Ask about TraceCraft"
      >
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
          />
        </svg>
        <span className="hidden sm:inline text-sm font-medium">Ask AI</span>
      </button>
    );
  }

  return (
    <div
      role="dialog"
      aria-label="TraceCraft documentation chat"
      className="fixed bottom-6 right-6 w-[360px] sm:w-96 h-[500px] bg-white dark:bg-gray-900 rounded-lg shadow-xl flex flex-col z-50 border border-gray-200 dark:border-gray-700"
    >
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-800 rounded-t-lg">
        <div className="flex items-center gap-2">
          <svg
            className="w-5 h-5 text-blue-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
            />
          </svg>
          <h3 className="font-semibold text-sm">Ask about TraceCraft</h3>
        </div>
        <div className="flex items-center gap-1">
          <Link
            href="/playground/chat"
            className="p-1.5 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
            title="Open full chat page"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
              />
            </svg>
          </Link>
          {messages.length > 0 && (
            <button
              onClick={handleClear}
              className="p-1.5 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
              title="Clear conversation"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                />
              </svg>
            </button>
          )}
          <button
            onClick={() => setIsOpen(false)}
            className="p-1.5 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
            title="Close"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-gray-500 dark:text-gray-400 text-sm space-y-3">
            <p>Ask me anything about TraceCraft:</p>
            <div className="space-y-1.5 text-xs" role="list" aria-label="Suggested questions">
              {[
                'How do I get started with TraceCraft?',
                'What decorators are available?',
                'How do I integrate with LangChain?',
                'What exporters does TraceCraft support?',
              ].map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => setInput(question)}
                  className="block w-full text-left cursor-pointer hover:text-blue-600 dark:hover:text-blue-400 focus:outline-none focus:text-blue-600"
                >
                  &bull; {question}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`${
              msg.role === 'user'
                ? 'ml-6 bg-blue-100 dark:bg-blue-900/50'
                : 'mr-2 bg-gray-100 dark:bg-gray-800'
            } p-3 rounded-lg text-sm`}
          >
            <div className="whitespace-pre-wrap">{msg.content}</div>
            {msg.citations && msg.citations.length > 0 && (
              <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                <p className="text-xs text-gray-500 dark:text-gray-400">Sources:</p>
                <div className="flex flex-wrap gap-1 mt-1">
                  {msg.citations.flatMap((c, ci) =>
                    c.sources.slice(0, 3).map((s, si) => {
                      const match = s.location?.match(/docs\/(.+?)(?:\.md|\.mdx)?$/);
                      const path = match ? `/${match[1].replace(/\/index$/, '')}` : null;
                      return path ? (
                        <a
                          key={`${ci}-${si}`}
                          href={path}
                          className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                        >
                          {path}
                        </a>
                      ) : null;
                    })
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="mr-2 bg-gray-100 dark:bg-gray-800 p-3 rounded-lg text-sm">
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
        )}
        {error && (
          <div className="text-red-500 text-xs p-2 bg-red-50 dark:bg-red-900/20 rounded">
            {error}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-3 border-t dark:border-gray-700">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question..."
            className="flex-1 px-3 py-2 border rounded-lg text-sm dark:bg-gray-800 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50 hover:bg-blue-700 transition-colors"
            aria-label="Send message"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          </button>
        </div>
      </form>
    </div>
  );
}
