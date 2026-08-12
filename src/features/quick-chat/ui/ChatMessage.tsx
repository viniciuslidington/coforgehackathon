'use client';

import type { ChatMessage } from '@/entities/call/model/types';
import styles from './ChatMessage.module.css';

interface ChatMessageProps {
  message: ChatMessage;
}

export function ChatMessageBubble({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`${styles.bubble} ${isUser ? styles.user : styles.ai}`}>
      <div className={styles.tag}>
        {isUser ? 'YOU' : 'BRIEFING'}
      </div>
      <div className={styles.text}>{message.text}</div>
    </div>
  );
}
