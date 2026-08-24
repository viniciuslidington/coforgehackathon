'use client';

import type { ChatMessage } from '@/entities/meeting/model/types';
import { ChatMessageBubble } from '@/features/quick-chat/ui/ChatMessage';
import styles from './DetailChat.module.css';

interface DetailChatProps {
  messages: ChatMessage[];
  draft: string;
  asking: boolean;
  onDraftChange: (value: string) => void;
  onSend: () => void;
}

export function DetailChat({
  messages,
  draft,
  asking,
  onDraftChange,
  onSend,
}: DetailChatProps) {
  return (
    <div className={styles.panel}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.title}>Ask about this meeting</div>
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
            placeholder="Ask about this meeting…"
            className={styles.input}
            disabled={asking}
          />
          <button className={styles.sendBtn} onClick={onSend} disabled={asking}>
            Ask
          </button>
        </div>
      </div>
    </div>
  );
}
