'use client';

import { useEffect, useRef } from 'react';
import type { MeetingSegment } from '@/entities/meeting/model/types';
import styles from './CallTranscript.module.css';

interface MeetingTranscriptProps {
  segments: MeetingSegment[];
  /** Segments covered by the citation the user last clicked. */
  activeIndexes?: ReadonlySet<number>;
  /** The segment to scroll into view. */
  focusIndex?: number | null;
  /** Changes on every click so the same citation can be re-followed. */
  focusNonce?: number;
}

export function MeetingTranscript({
  segments,
  activeIndexes,
  focusIndex = null,
  focusNonce = 0,
}: MeetingTranscriptProps) {
  const focusRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (focusIndex === null) return;
    // DOM work only — no setState, so `react-hooks/set-state-in-effect` holds.
    focusRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [focusIndex, focusNonce]);

  return (
    <div className={styles.transcript}>
      {segments.map((seg, i) => {
        const isActive = activeIndexes?.has(i) ?? false;
        return (
          <div
            key={i}
            className={`${styles.entry} ${isActive ? styles.entryActive : ''}`}
            ref={i === focusIndex ? focusRef : undefined}
          >
            <div className={styles.meta}>
              <span className={`${styles.ts} ${isActive ? styles.tsActive : ''}`}>{seg.t}</span>
              <span className={`${styles.speaker} ${seg.flag ? styles.speakerFlag : ''} ${isActive ? styles.speakerActive : ''}`}>
                {seg.sp}
              </span>
              {seg.flag && <span className={styles.flagBadge}>{seg.flag}</span>}
            </div>
            <div className={`${styles.text} ${isActive ? styles.textActive : ''}`}>{seg.tx}</div>
          </div>
        );
      })}
    </div>
  );
}
