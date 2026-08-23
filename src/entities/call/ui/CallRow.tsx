'use client';

import type { MeetingSummary } from '@/entities/meeting/model/types';
import styles from './CallRow.module.css';

interface CallRowProps {
  meeting: MeetingSummary;
}

export function CallRow({ meeting }: CallRowProps) {
  const date = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    .format(new Date(`${meeting.meeting_date}T00:00:00`));
  const duration = `${Math.floor(meeting.duration_seconds / 60)}m ${meeting.duration_seconds % 60}s`;

  return (
    <article className={styles.row}>
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
    </article>
  );
}
