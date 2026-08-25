'use client';

import type { MeetingSummary } from '../model/types';
import { PriorityBadge } from './PriorityBadge';
import styles from './CallRow.module.css';

interface CallRowProps {
  meeting: MeetingSummary;
  onOpen?: (meeting: MeetingSummary) => void;
}

export function CallRow({ meeting, onOpen }: CallRowProps) {
  const date = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    .format(new Date(`${meeting.meeting_date}T00:00:00`));
  const duration = `${Math.floor(meeting.duration_seconds / 60)}m ${meeting.duration_seconds % 60}s`;

  return (
    <article
      className={styles.row}
      onClick={() => onOpen?.(meeting)}
      style={onOpen ? { cursor: 'pointer' } : undefined}
    >
      <div>
        <div className={styles.time}>{date}</div>
      </div>

      <div className={styles.duration}>{duration}</div>

      <div>
        <div className={styles.counterparty}>{meeting.title}</div>
        <div className={styles.channel}>{meeting.participants.join(', ') || 'No participants'}</div>
      </div>

      <div className={styles.participants}>{meeting.participants.join(', ') || 'No participants'}</div>

      <div className={styles.summaryCol}>
        <div className={styles.summaryText}>{meeting.simple_summary}</div>
      </div>

      <div className={styles.keywords}>
        {meeting.keywords.length ? meeting.keywords.map((keyword) => (
          <span key={keyword} className={styles.keyword}>{keyword}</span>
        )) : <span className={styles.emptyKeyword}>No keywords yet</span>}
      </div>

      {meeting.priority_tier && meeting.priority_score != null && (
        <div className={styles.priority}>
          <PriorityBadge tier={meeting.priority_tier} score={meeting.priority_score} />
        </div>
      )}
    </article>
  );
}
