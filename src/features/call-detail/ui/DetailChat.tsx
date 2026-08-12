'use client';

import type { ChatMessage } from '@/entities/call/model/types';
import { ChatMessageBubble } from '@/features/quick-chat/ui/ChatMessage';
import styles from './DetailChat.module.css';

interface DetailChatProps {
  messages: ChatMessage[];
  draft: string;
  rangeText: string | null;
  onDraftChange: (value: string) => void;
  onSend: () => void;
  onClearRange: () => void;
}

export function DetailChat({
  messages,
  draft,
  rangeText,
  onDraftChange,
  onSend,
  onClearRange,
}: DetailChatProps) {
  return (
    <div className={styles.panel}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.title}>Ask about this call</div>
        {rangeText && (
          <div className={styles.rangePill}>
            <span className={styles.rangeLabel}>RANGE {rangeText}</span>
            <button className={styles.rangeClear} onClick={onClearRange}>
              ×
            </button>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className={styles.body}>
        {messages.map((m, i) => (
          <ChatMessageBubble key={i} message={m} />
        ))}
      </div>

      {/* Input */}
      <div className={styles.inputArea}>
        <div className={styles.inputRow}>
          <input
            value={draft}
            onChange={e => onDraftChange(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') onSend(); }}
            placeholder={rangeText ? `Ask about ${rangeText}…` : 'Ask about this call…'}
            className={styles.input}
          />
          <button className={styles.sendBtn} onClick={onSend}>
            Ask
          </button>
        </div>
      </div>
    </div>
  );
}
