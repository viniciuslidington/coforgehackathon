'use client';

import type { ChatMessage } from '@/entities/meeting/model/types';
import { renderWithMeetingLinks } from '@/entities/meeting/lib/meetingMarkers';
import styles from './ChatMessageBubble.module.css';

interface ChatMessageBubbleProps {
  message: ChatMessage;
  /**
   * When given, `[[meeting:<id>]]` markers in the text render as clickable
   * titles. Omit it and the message renders as plain text.
   */
  onOpenMeeting?: (meetingId: string) => void;
}

export function ChatMessageBubble({ message, onOpenMeeting }: ChatMessageBubbleProps) {
  const isUser = message.role === 'user';
  const meetings = message.meetings ?? [];

  return (
    <div className={`${styles.bubble} ${isUser ? styles.user : styles.ai}`}>
      <div className={styles.tag}>{isUser ? 'YOU' : 'BRIEFING'}</div>
      <div className={styles.text}>
        {onOpenMeeting
          ? renderWithMeetingLinks(message.text, meetings, onOpenMeeting, styles.meetingLink)
          : message.text}
      </div>
    </div>
  );
}
