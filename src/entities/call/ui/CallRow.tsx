'use client';

import type { Call } from '../model/types';
import { FlagBadge } from './FlagBadge';
import { PriorityBadge } from './PriorityBadge';
import styles from './CallRow.module.css';

interface CallRowProps {
  call: Call;
  onClick: () => void;
}

export function CallRow({ call, onClick }: CallRowProps) {
  const isUrgent = call.tier === 'urgent';
  const highMentions = call.mentions >= 3;

  return (
    <div
      className={`${styles.row} ${isUrgent ? styles.urgent : ''}`}
      onClick={onClick}
    >
      {/* Time */}
      <div>
        <div className={styles.time}>{call.time}</div>
        <div className={styles.duration}>{call.dur}</div>
      </div>

      {/* Counterparty */}
      <div>
        <div
          className={styles.counterparty}
          style={{ color: highMentions ? 'var(--urgent)' : 'var(--text-secondary-strong)' }}
        >
          {call.cp}
        </div>
        <div className={styles.channel}>{call.channel}</div>
      </div>

      {/* AI Summary */}
      <div className={styles.summaryCol}>
        <div className={styles.summaryText}>{call.summary}</div>
        {call.flags.length > 0 && (
          <div className={styles.flags}>
            {call.flags.map((f) => (
              <FlagBadge key={f.label} flag={f} />
            ))}
          </div>
        )}
      </div>

      {/* Mentions */}
      <div className={styles.mentionsCol}>
        <div
          className={styles.mentionsBadge}
          data-level={
            highMentions ? 'high' : call.mentions > 0 ? 'some' : 'none'
          }
        >
          {call.mentions}
        </div>
      </div>

      {/* Priority */}
      <div>
        <PriorityBadge tier={call.tier} score={call.score} />
      </div>
    </div>
  );
}
