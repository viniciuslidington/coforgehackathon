'use client';

import type { MeetingSummary } from '../model/types';
import { formatMeetingDate, getCallType } from '../lib/helpers';
import { PriorityBadge } from './PriorityBadge';
import styles from './CallRow.module.css';

interface CallRowProps {
  meeting: MeetingSummary;
  onOpen?: (meeting: MeetingSummary) => void;
  showPriority?: boolean;
}

export function CallRow({ meeting, onOpen, showPriority = true }: CallRowProps) {
  const date = formatMeetingDate(meeting.meeting_date);
  const duration = `${Math.floor(meeting.duration_seconds / 60)}m ${meeting.duration_seconds % 60}s`;
  const callType = getCallType(meeting);

  return (
    <article
      className={`${styles.row} ${showPriority ? '' : styles.noPriority}`}
      onClick={() => onOpen?.(meeting)}
      style={onOpen ? { cursor: 'pointer' } : undefined}
    >
      <div>
        <div className={styles.time}>{date}</div>
      </div>

      <div>
        <span className={styles.typeBadge} data-type={callType.type}>
          {callType.label}
        </span>
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

      {showPriority && meeting.priority_tier && meeting.priority_score != null && (
        <div className={styles.priority}>
          <PriorityBadge tier={meeting.priority_tier} score={meeting.priority_score} />
        </div>
      )}
    </article>
  );
}
