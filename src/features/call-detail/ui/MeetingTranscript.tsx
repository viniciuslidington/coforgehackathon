'use client';

import type { MeetingSegment } from '@/entities/meeting/model/types';
import styles from './CallTranscript.module.css';

interface MeetingTranscriptProps {
  segments: MeetingSegment[];
}

export function MeetingTranscript({ segments }: MeetingTranscriptProps) {
  return (
    <div className={styles.transcript}>
      {segments.map((seg, i) => (
        <div key={i} className={styles.entry}>
          <div className={styles.meta}>
            <span className={styles.ts}>{seg.t}</span>
            <span className={`${styles.speaker} ${seg.flag ? styles.speakerFlag : ''}`}>
              {seg.sp}
            </span>
            {seg.flag && (
              <span className={styles.flagBadge}>{seg.flag}</span>
            )}
          </div>
          <div className={styles.text}>{seg.tx}</div>
        </div>
      ))}
    </div>
  );
}
