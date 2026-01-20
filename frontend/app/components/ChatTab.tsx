'use client';

import { useState, useRef, useEffect } from 'react';
import type { ChatMessage, ChatContext } from '../types/blocks';
import { apiFetch } from '../lib/api';

interface ChatTabProps {
  currentHtml: string;
  context: ChatContext;
  onHtmlUpdate: (newHtml: string) => void;
  apiKey: string;
}

export default function ChatTab({ currentHtml, context, onHtmlUpdate, apiKey }: ChatTabProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);
    setStreamingContent('');

    try {
      const response = await apiFetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          apiKey,
          currentHtml,
          messages: messages.map((m) => ({ role: m.role, content: m.content })),
          newMessage: userMessage.content,
          context,
        }),
      });

      if (!response.ok) {
        throw new Error('Chat request failed');
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let accumulatedContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === 'chunk') {
                accumulatedContent += data.content;
                setStreamingContent(accumulatedContent);
              } else if (data.type === 'complete') {
                // Add assistant message
                const assistantMessage: ChatMessage = {
                  id: `msg-${Date.now()}`,
                  role: 'assistant',
                  content: data.explanation || 'Changes applied.',
                  timestamp: new Date(),
                  htmlSnapshot: data.html,
                };

                setMessages((prev) => [...prev, assistantMessage]);
                setStreamingContent('');

                // Update the HTML if we got a valid response
                if (data.html) {
                  onHtmlUpdate(data.html);
                }
              } else if (data.type === 'error') {
                throw new Error(data.error);
              }
            } catch (parseError) {
              // Ignore JSON parse errors from partial chunks
            }
          }
        }
      }
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage: ChatMessage = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Something went wrong'}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsStreaming(false);
      setStreamingContent('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Quick suggestions
  const suggestions = [
    'Make the CTA button bigger and more prominent',
    'Change the tone to be more friendly',
    'Add more whitespace between sections',
    'Make the header text larger',
    'Change the background color of the hero section',
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center text-slate-500 py-8">
            <div className="text-4xl mb-4">💬</div>
            <p className="font-medium mb-2">Chat with AI to edit your email</p>
            <p className="text-sm mb-6">Describe the changes you want and the template will update live.</p>

            {/* Suggestions */}
            <div className="space-y-2">
              <p className="text-xs text-slate-400 mb-2">Try asking:</p>
              {suggestions.slice(0, 3).map((suggestion, i) => (
                <button
                  key={i}
                  onClick={() => setInput(suggestion)}
                  className="block w-full text-left px-3 py-2 text-sm bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
                >
                  &ldquo;{suggestion}&rdquo;
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2 ${
                    message.role === 'user'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-100 text-slate-900'
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                  {message.htmlSnapshot && (
                    <p className="text-xs mt-1 opacity-70">✓ Template updated</p>
                  )}
                </div>
              </div>
            ))}

            {/* Streaming indicator */}
            {isStreaming && (
              <div className="flex justify-start">
                <div className="max-w-[80%] rounded-lg px-4 py-2 bg-slate-100 text-slate-900">
                  {streamingContent ? (
                    <p className="text-sm whitespace-pre-wrap">{streamingContent}</p>
                  ) : (
                    <div className="flex items-center gap-2">
                      <div className="flex gap-1">
                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                      <span className="text-sm text-slate-500">Thinking...</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-slate-200 p-4">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe the changes you want..."
            disabled={isStreaming}
            rows={2}
            className="flex-1 px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm resize-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors self-end"
          >
            {isStreaming ? (
              <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            )}
          </button>
        </form>
        <p className="text-xs text-slate-400 mt-2">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
