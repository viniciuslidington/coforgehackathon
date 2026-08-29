'use client';

import type { Briefing } from '@/entities/meeting/model/scope';
import { firstMeetingId, renderWithMeetingLinks, stripMeetingMarkers } from '@/entities/meeting/lib/meetingMarkers';
import { AgentTrace } from '@/shared/ui/AgentTrace';
import styles from './BriefingPanel.module.css';

interface BriefingPanelProps {
  briefing: Briefing | null;
  steps: string[];
  loading: boolean;
  error: string | null;
  onOpenMeeting: (meetingId: string) => void;
}

export function BriefingPanel({ briefing, steps, loading, error, onOpenMeeting }: BriefingPanelProps) {
  if (error) {
    return <p className={styles.message}>{error}</p>;
  }

  if (loading && !briefing) {
    return (
      <div className={styles.panel}>
        <div className={styles.label}>BRIEFING</div>
        {steps.length > 0
          ? <AgentTrace steps={steps} />
          : <p className={styles.message}>Preparing your briefing…</p>}
      </div>
    );
  }

  if (!briefing) {
    return <p className={styles.message}>No briefing available for this scope.</p>;
  }

  const paragraphs = briefing.summary.split('\n\n').filter(Boolean);

  return (
    <div className={styles.panel}>
      {briefing.key_points.length > 0 && (
        <>
          <div className={styles.label}>KEY POINTS</div>
          <div className={styles.keyPoints}>
            {briefing.key_points.map((point, index) => {
              // The chip is itself the control, so a marker inside it is
              // stripped rather than rendered as a nested link — its id still
              // becomes the click target.
              const label = stripMeetingMarkers(point.text);
              const target = point.meeting_id ?? firstMeetingId(point.text);
              return (
                <button
                  key={`${index}-${label}`}
                  type="button"
                  className={styles.keyPoint}
                  data-tone={point.tone}
                  // A point without a meeting is context, not a link.
                  disabled={!target}
                  title={target ? 'Open this meeting' : undefined}
                  onClick={() => target && onOpenMeeting(target)}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </>
      )}

      <div className={styles.label}>BRIEFING</div>
      <div className={styles.summary}>
        {paragraphs.map((paragraph, index) => (
          <p key={index}>
            {renderWithMeetingLinks(
              paragraph,
              briefing.referenced_meetings,
              onOpenMeeting,
              styles.meetingLink,
            )}
          </p>
        ))}
      </div>

      {briefing.truncated && (
        <p className={styles.note}>This briefing was shortened to fit the response limit.</p>
      )}
    </div>
  );
}
