import React, { useState } from 'react';
import { X, Bot, Sparkles } from 'lucide-react';
import { ChatWindow } from './ChatWindow';

export const ChatWidget = () => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      {/* Floating Chat Window Panel */}
      {isOpen && (
        <div className="mb-3 animate-in fade-in slide-in-from-bottom-3 duration-200">
          <ChatWindow onClose={() => setIsOpen(false)} />
        </div>
      )}

      {/* Floating Action Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`group relative flex items-center justify-center rounded-full transition-all duration-300 active:scale-95 ${
          isOpen
            ? 'p-1 bg-th-surface-el text-th-text-primary hover:bg-th-border ring-2 ring-th-brand/40 shadow-lg shadow-th-brand/10'
            : 'p-0.5 hover:scale-105 shadow-elevated'
        }`}
        title={isOpen ? 'Close AI Risk Copilot' : 'Open AI Risk Copilot'}
        aria-label="Toggle AI Risk Copilot"
      >
        {/* Pulse alert indicator and glow when closed */}
        {!isOpen && (
          <>
            {/* Ambient halo glow */}
            <span className="absolute -inset-1 rounded-full bg-gradient-to-r from-emerald-500/30 to-teal-400/30 blur-md group-hover:from-emerald-500/50 group-hover:to-teal-400/50 transition-all"></span>

            {/* Status notification dot */}
            <span className="absolute -top-1 -right-1 flex h-4 w-4 z-20">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-4 w-4 bg-emerald-500 border-2 border-th-surface shadow-sm"></span>
            </span>
          </>
        )}

        {isOpen ? (
          <div className="w-12 h-12 rounded-full bg-th-surface-el flex items-center justify-center text-th-text-primary border border-th-border">
            <X className="w-5 h-5 transition-transform duration-200 group-hover:rotate-90 text-th-text-primary" />
          </div>
        ) : (
          <div className="relative w-14 h-14 rounded-full overflow-hidden flex items-center justify-center shadow-lg transition-all duration-300 bg-gradient-to-br from-[#0F5C42] via-[#0D4F38] to-[#083526] text-white border-2 border-emerald-400/30 group-hover:border-emerald-300/60">
            {/* Inner background highlight */}
            <div className="absolute inset-0 bg-radial from-white/15 to-transparent pointer-events-none" />

            {/* AI Bot and Sparkles Icon Composition */}
            <div className="relative flex items-center justify-center">
              <Bot className="w-6 h-6 text-white transition-transform duration-300 group-hover:scale-110" />
              <Sparkles className="w-3.5 h-3.5 text-emerald-300 absolute -top-1.5 -right-2 animate-pulse" />
            </div>
          </div>
        )}
      </button>
    </div>
  );
};

export default ChatWidget;

