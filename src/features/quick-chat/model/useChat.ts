'use client';

import { useState, useCallback } from 'react';
import type { ChatMessage, ContextLabel } from '@/entities/call/model/types';
import { BRIEF } from '@/entities/call/model/data';

export function useChat() {
  const [context, setContext] = useState<ContextLabel>('Last 5 calls');
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'ai', text: BRIEF['Last 5 calls'] },
  ]);
  const [draft, setDraft] = useState('');

  const selectContext = useCallback((ctx: ContextLabel) => {
    setContext(ctx);
    setMessages([{ role: 'ai', text: BRIEF[ctx] }]);
  }, []);

  const sendMessage = useCallback(() => {
    const q = draft.trim();
    if (!q) return;
    setDraft('');
    setMessages(prev => [
      ...prev,
      { role: 'user', text: q },
      {
        role: 'ai',
        text: `Across ${context.toLowerCase()}: the only items that move your book are the CITI-FX EUR/USD block (unanswered, 15:00 deadline) and the desk-wide instruction to flatten 2s10s. The Nomura JGB bid stays flagged as an anomaly, not an opportunity, until someone confirms it on a second line.`,
      },
    ]);
  }, [draft, context]);

  const askSuggestion = useCallback((question: string) => {
    setDraft('');
    setMessages(prev => [
      ...prev,
      { role: 'user', text: question },
      {
        role: 'ai',
        text: `Across ${context.toLowerCase()}: the only items that move your book are the CITI-FX EUR/USD block (unanswered, 15:00 deadline) and the desk-wide instruction to flatten 2s10s. The Nomura JGB bid stays flagged as an anomaly, not an opportunity, until someone confirms it on a second line.`,
      },
    ]);
  }, [context]);

  return {
    context,
    messages,
    draft,
    setDraft,
    selectContext,
    sendMessage,
    askSuggestion,
  } as const;
}
