'use client';

import type { MeetingSegment } from '@/entities/meeting/model/types';
import styles from './CallTranscript.module.css';

interface MeetingTranscriptProps {
  segments: MeetingSegment[];
  isInRange: (index: number) => boolean;
  onPick: (index: number) => void;
}

export function MeetingTranscript({ segments, isInRange, onPick }: MeetingTranscriptProps) {
  return (
    <div className={styles.transcript}>
      {segments.map((seg, i) => {
        const active = isInRange(i);
        return (
          <div
            key={i}
            className={styles.entry}
            style={{
              borderLeftColor: active ? 'var(--teal-light)' : 'var(--border-6)',
              background: active ? '#1e2726' : 'transparent',
            }}
            onClick={() => onPick(i)}
          >
            <div className={styles.meta}>
              <span className={`${styles.ts} ${active ? styles.tsActive : ''}`}>
                {seg.t}
              </span>
              <span className={`${styles.speaker} ${seg.flag ? styles.speakerFlag : ''} ${active ? styles.speakerActive : ''}`}>
                {seg.sp}
              </span>
              {seg.flag && (
                <span className={styles.flagBadge}>{seg.flag}</span>
              )}
            </div>
            <div className={`${styles.text} ${active ? styles.textActive : ''}`}>
              {seg.tx}
            </div>
          </div>
        );
      })}
    </div>
  );
}
