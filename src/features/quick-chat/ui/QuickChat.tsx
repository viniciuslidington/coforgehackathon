'use client';

import type { ContextLabel } from '@/entities/call/model/types';
import { CONTEXTS, KEYPOINTS } from '@/entities/call/model/data';
import { useChat } from '../model/useChat';
import { ChatMessageBubble } from './ChatMessage';
import { ChatInput } from './ChatInput';
import styles from './QuickChat.module.css';

const SUGGESTIONS = [
  'Anything I must answer?',
  'What changed in my book?',
];

export function QuickChat() {
  const {
    context,
    messages,
    draft,
    setDraft,
    selectContext,
    sendMessage,
    askSuggestion,
  } = useChat();

  const keyPoints = KEYPOINTS[context] ?? [];

  return (
    <div className={styles.panel}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerRow}>
          <div className={styles.title}>Quick chat</div>
          <div className={styles.contextLabel}>CONTEXT</div>
        </div>
        <div className={styles.contextPills}>
          {CONTEXTS.map(label => (
            <button
              key={label}
              className={`${styles.ctxPill} ${context === label ? styles.ctxActive : ''}`}
              onClick={() => selectContext(label as ContextLabel)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div className={styles.body}>
        {/* Key Points */}
        <div className={styles.kpLabel}>KEY POINTS</div>
        <div className={styles.kpList}>
          {keyPoints.map(k => (
            <div
              key={k.label}
              className={styles.kpBadge}
              data-tone={k.tone}
            >
              {k.label}
            </div>
          ))}
        </div>

        {/* Messages */}
        <div className={styles.messages}>
          {messages.map((m, i) => (
            <ChatMessageBubble key={i} message={m} />
          ))}
        </div>
      </div>

      {/* Input */}
      <ChatInput
        value={draft}
        onChange={setDraft}
        onSend={sendMessage}
        suggestions={SUGGESTIONS.map(label => ({
          label,
          onAsk: () => askSuggestion(label),
        }))}
      />
    </div>
  );
}
