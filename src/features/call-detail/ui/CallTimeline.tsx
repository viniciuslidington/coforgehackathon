'use client';

import type { CallSegment } from '@/entities/call/model/types';
import styles from './CallTimeline.module.css';

interface CallTimelineProps {
  segments: CallSegment[];
  isInRange: (index: number) => boolean;
  onPick: (index: number) => void;
}

export function CallTimeline({ segments, isInRange, onPick }: CallTimelineProps) {
  return (
    <div className={styles.timeline}>
      {segments.map((seg, i) => {
        const active = isInRange(i);
        return (
          <div
            key={i}
            className={styles.entry}
            onClick={() => onPick(i)}
          >
            {/* Timestamp */}
            <div className={`${styles.ts} ${active ? styles.tsActive : ''}`}>
              {seg.t}
            </div>

            {/* Rail + Node */}
            <div className={styles.rail}>
              <div className={`${styles.railLine} ${active ? styles.railActive : ''}`} />
              <div className={`${styles.node} ${active ? styles.nodeActive : ''}`} />
              <div className={`${styles.railLine} ${active ? styles.railActive : ''}`} />
            </div>

            {/* Content Card */}
            <div className={`${styles.card} ${active ? styles.cardActive : ''}`}>
              <div className={styles.cardHeader}>
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
          </div>
        );
      })}
    </div>
  );
}
