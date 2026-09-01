'use client';

import type { ChatMessage } from '@/entities/meeting/model/types';
import { meetingMarkerRule, meetingTimeRule } from '@/entities/meeting/lib/meetingMarkers';
import { timeRangeRule } from '@/entities/meeting/lib/transcriptTime';
import { renderRichText, type InlineRule } from '@/shared/lib/richText';
import styles from './ChatMessageBubble.module.css';

interface ChatMessageBubbleProps {
  message: ChatMessage;
  /**
   * When given, `[[meeting:<id>]]` markers render as clickable titles.
   */
  onOpenMeeting?: (meetingId: string) => void;
  /**
   * When given, bracketed timestamps render as controls that jump the
   * transcript. Only the per-meeting chat has a transcript to jump.
   */
  onSeek?: (fromSeconds: number, toSeconds: number | null) => void;
  /**
   * When given, `[[meeting:<id>@<time>]]` citations render as controls that
   * open that meeting at that moment. Quick Chat spans many meetings, so its
   * moments carry the meeting with them.
   */
  onOpenMeetingAt?: (
    meetingId: string,
    fromSeconds: number | null,
    toSeconds: number | null,
  ) => void;
}

export function ChatMessageBubble({
  message,
  onOpenMeeting,
  onSeek,
  onOpenMeetingAt,
}: ChatMessageBubbleProps) {
  const isUser = message.role === 'user';

  // Built per render on purpose: a rule carries the run counter that caps
  // adjacent citations, so a memoized one would arrive mid-run.
  const rules: InlineRule[] = [];
  // Ahead of the plain marker rule: both match a timestamped citation at the
  // same index, and the scanner breaks ties by array order.
  if (onOpenMeetingAt) {
    rules.push(meetingTimeRule(message.meetings ?? [], onOpenMeetingAt, styles.meetingTimeLink));
  }
  if (onOpenMeeting) {
    rules.push(meetingMarkerRule(message.meetings ?? [], onOpenMeeting, styles.meetingLink));
  }
  if (onSeek) {
    rules.push(timeRangeRule(onSeek, styles.timeLink));
  }

  return (
    <div className={`${styles.bubble} ${isUser ? styles.user : styles.ai}`}>
      <div className={styles.tag}>{isUser ? 'YOU' : 'BRIEFING'}</div>
      {isUser ? (
        // A typed message is not Markdown — parsing it would mangle
        // punctuation the user meant literally.
        <div className={styles.text}>{message.text}</div>
      ) : (
        <div className={`${styles.text} ${styles.prose}`}>{renderRichText(message.text, rules)}</div>
      )}
    </div>
  );
}
