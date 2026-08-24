'use client';

import type { MeetingSegment } from '@/entities/meeting/model/types';
import styles from './CallTimeline.module.css';

interface MeetingTimelineProps {
  segments: MeetingSegment[];
}

const SPEAKER_ACCENTS = [
  { bg: 'rgba(63, 182, 186, 0.12)', text: '#78c9cb', border: 'rgba(63, 182, 186, 0.25)' },
  { bg: 'rgba(167, 139, 250, 0.12)', text: '#c4b5fd', border: 'rgba(167, 139, 250, 0.25)' },
  { bg: 'rgba(96, 165, 250, 0.12)', text: '#93c5fd', border: 'rgba(96, 165, 250, 0.25)' },
  { bg: 'rgba(251, 191, 36, 0.12)', text: '#fde68a', border: 'rgba(251, 191, 36, 0.25)' },
  { bg: 'rgba(52, 211, 153, 0.12)', text: '#a7f3d0', border: 'rgba(52, 211, 153, 0.25)' },
  { bg: 'rgba(244, 114, 182, 0.12)', text: '#fbcfe8', border: 'rgba(244, 114, 182, 0.25)' },
];

function getSpeakerTheme(name: string) {
  if (!name) return undefined;
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash << 5) - hash + name.charCodeAt(i);
    hash |= 0;
  }
  return SPEAKER_ACCENTS[Math.abs(hash) % SPEAKER_ACCENTS.length];
}

export function MeetingTimeline({ segments }: MeetingTimelineProps) {
  if (!segments || segments.length === 0) {
    return <div className={styles.empty}>No timeline segments recorded for this meeting.</div>;
  }

  return (
    <div className={styles.timeline} role="feed" aria-label="Meeting timeline">
      {segments.map((seg, i) => {
        const speakerTheme = getSpeakerTheme(seg.sp);
        const speakerInitial = seg.sp ? seg.sp.charAt(0).toUpperCase() : '•';
        const isFirst = i === 0;
        const isLast = i === segments.length - 1;

        return (
          <div key={i} className={styles.entry}>
            {/* Timestamp */}
            <time dateTime={seg.t} className={styles.ts}>
              {seg.t}
            </time>

            {/* Continuous Rail + Node */}
            <div className={styles.rail} aria-hidden="true">
              <div className={`${styles.railLine} ${isFirst ? styles.railHidden : ''}`} />
              <div className={styles.node} />
              <div className={`${styles.railLine} ${isLast ? styles.railHidden : ''}`} />
            </div>

            {/* Content Card */}
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                {seg.sp && (
                  <span
                    className={styles.speakerBadge}
                    style={
                      speakerTheme
                        ? {
                            backgroundColor: speakerTheme.bg,
                            color: speakerTheme.text,
                            borderColor: speakerTheme.border,
                          }
                        : undefined
                    }
                  >
                    <span className={styles.speakerAvatar}>{speakerInitial}</span>
                    {seg.sp}
                  </span>
                )}
                {seg.flag && (
                  <span className={styles.flagBadge}>
                    <span className={styles.flagDot} />
                    {seg.flag}
                  </span>
                )}
              </div>
              <div className={styles.text}>
                {seg.tx}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
