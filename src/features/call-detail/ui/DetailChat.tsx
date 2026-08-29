'use client';

import { useEffect, useRef } from 'react';
import type { ChatMessage } from '@/entities/meeting/model/types';
import { ChatMessageBubble } from '@/shared/ui/ChatMessageBubble';
import { AgentTrace } from '@/shared/ui/AgentTrace';
import styles from './DetailChat.module.css';

interface DetailChatProps {
  messages: ChatMessage[];
  draft: string;
  asking: boolean;
  steps: string[];
  onDraftChange: (value: string) => void;
  onSend: () => void;
}

export function DetailChat({
  messages,
  draft,
  asking,
  steps,
  onDraftChange,
  onSend,
}: DetailChatProps) {
  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, steps]);

  return (
    <div className={styles.panel}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.title}>Ask about this meeting</div>
      </div>

      {/* Messages */}
      <div className={styles.body} ref={bodyRef}>
        {messages.map((m, i) => (
          <ChatMessageBubble key={i} message={m} />
        ))}
        {asking && <AgentTrace steps={steps} />}
      </div>

      {/* Input */}
      <div className={styles.inputArea}>
        <div className={styles.inputRow}>
          <input
            value={draft}
            onChange={e => onDraftChange(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') onSend(); }}
            placeholder="Ask about this meeting…"
            className={styles.input}
            disabled={asking}
          />
          <button className={styles.sendBtn} onClick={onSend} disabled={asking || !draft.trim()}>
            Ask
          </button>
        </div>
      </div>
    </div>
  );
}
