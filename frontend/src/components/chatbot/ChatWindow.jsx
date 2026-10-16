import React, { useState, useRef, useEffect } from 'react';
import {
  X,
  Send,
  Zap,
  Bot,
  Sparkles
} from 'lucide-react';
import { ChatMessage } from './ChatMessage';
import { sendChatMessage } from '../../api/client';

export const ChatWindow = ({ onClose }) => {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        "Greetings. I am your Quantitative Cyber Risk Analyst. I have real-time access to your FAIR Monte Carlo quantifications, asset portfolio loss bounds, and security controls ROSI data.\n\nSuggested inquiries:\n• What is our biggest financial cyber risk right now?\n• Which control delivers the highest Return on Security Investment (ROSI)?\n• How does the Knapsack ILP optimizer outperform naive budget allocation?",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSend = async (textToSend) => {
    const text = (textToSend || inputValue).trim();
    if (!text || loading) return;

    const userTimestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsg = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: userTimestamp,
    };

    const historyPayload = messages
      .filter((m) => m.id !== 'welcome' && !m.isError)
      .map((m) => ({ role: m.role, content: m.content }));

    setMessages((prev) => [...prev, userMsg]);
    setInputValue('');
    setLoading(true);

    try {
      const res = await sendChatMessage(text, historyPayload);
      const assistantMsg = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: res.reply || "I didn't receive a response.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      let errDetail = err.response?.data?.detail;
      if (err.response?.status === 502) {
        errDetail =
          errDetail ||
          'AI service configuration issue. Please verify backend environment and token.';
      } else if (err.code === 'ERR_NETWORK' || !err.response) {
        errDetail = 'Cannot reach backend server. Please verify FastAPI is running on http://localhost:8000.';
      } else {
        errDetail = errDetail || 'Sorry, I encountered an error processing your query. Please try again.';
      }

      const errorMsg = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        isError: true,
        content: `⚠️ ${errDetail}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const starterQuestions = [
    "What is our biggest cyber risk?",
    "Which control has highest ROSI?",
    "Summarize baseline EAL vs VaR95.",
  ];

  return (
    <div className="w-[370px] sm:w-[420px] h-[540px] max-h-[85vh] bg-th-surface border border-th-border rounded-2xl shadow-elevated flex flex-col overflow-hidden text-th-text-primary backdrop-blur-xl">

      {/* Distinct AI Copilot Header */}
      <div className="p-3.5 px-4 bg-th-surface-el border-b border-th-border flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="relative w-9 h-9 rounded-xl overflow-hidden flex items-center justify-center shrink-0 shadow-sm bg-gradient-to-br from-[#0F5C42] to-[#083526] text-white border border-emerald-400/30">
            <Bot className="w-5 h-5 text-white" />
            <Sparkles className="w-2.5 h-2.5 text-emerald-300 absolute top-1 right-1" />
            <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-th-success border-2 border-th-surface-el"></span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-th-text-primary tracking-wide font-sans">
                AI Risk Copilot
              </h3>
              <span className="px-2 py-0.5 text-[9px] font-bold bg-th-brand-tint text-th-brand rounded-full border border-th-brand/30 uppercase tracking-wider">
                FAIR AI
              </span>
            </div>
            <p className="text-[10px] text-th-text-muted font-mono flex items-center gap-1.5 mt-0.5">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-th-brand animate-pulse"></span>
              Live Quantitative Assistant
            </p>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-2 rounded-full text-th-text-secondary hover:text-th-text-primary hover:bg-th-border transition-all"
          title="Close chat"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-th-surface scrollbar-thin scrollbar-thumb-th-border-strong">
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        {loading && (
          <div className="flex items-start space-x-2.5">
            <div className="w-7 h-7 rounded-lg overflow-hidden flex items-center justify-center shrink-0 shadow-sm bg-gradient-to-br from-[#0F5C42] to-[#083526] text-white ring-1 ring-emerald-400/30">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="bg-th-surface-el text-th-text-primary border border-th-border rounded-2xl rounded-tl-sm px-4 py-3 text-[13px] flex items-center space-x-2.5 shadow-soft">
              <span className="inline-flex gap-1 items-center">
                <span className="w-1.5 h-1.5 bg-th-brand rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                <span className="w-1.5 h-1.5 bg-th-brand rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                <span className="w-1.5 h-1.5 bg-th-brand rounded-full animate-bounce"></span>
              </span>
              <span className="text-xs text-th-text-secondary">Analyzing FAIR portfolio metrics...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Prompt Chips */}
      {messages.length <= 2 && (
        <div className="px-3 py-2.5 bg-th-surface border-t border-th-border overflow-x-auto flex items-center space-x-1.5">
          <span className="text-[10px] text-th-text-muted font-medium whitespace-nowrap flex items-center gap-1 shrink-0">
            <Zap className="w-3 h-3 text-th-warning" />
            Suggested:
          </span>
          {starterQuestions.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(q)}
              disabled={loading}
              className="text-[11px] px-3 py-1 rounded-full bg-th-surface-el text-th-text-secondary hover:bg-th-brand hover:text-white border border-th-border hover:border-th-brand whitespace-nowrap transition-all duration-200 shadow-sm active:scale-95"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input Form */}
      <div className="p-3 bg-th-surface-el border-t border-th-border">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center space-x-2.5"
        >
          <input
            ref={inputRef}
            type="text"
            placeholder="Ask about financial risk, EAL, VaR, or controls..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            className="flex-1 bg-th-surface border border-th-border rounded-full px-4 py-2.5 text-[13px] text-th-text-primary placeholder-th-text-muted focus:outline-none focus:border-th-brand focus:ring-1 focus:ring-th-brand transition-all shadow-inner"
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || loading}
            className="p-2.5 rounded-full bg-th-brand hover:bg-th-brand-hover text-white disabled:opacity-50 transition-all shadow-soft active:scale-95 flex items-center justify-center shrink-0"
            title="Send query"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>

    </div>
  );
};
