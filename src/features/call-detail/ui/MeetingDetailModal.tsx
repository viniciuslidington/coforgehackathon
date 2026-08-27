'use client';

import { useState } from 'react';
import type { ChatMessage, MeetingSegment, MeetingSummary } from '@/entities/meeting/model/types';
import { formatMeetingDate } from '@/entities/meeting/lib/helpers';
import { MeetingTimeline } from './MeetingTimeline';
import { MeetingTranscript } from './MeetingTranscript';
import { DetailChat } from './DetailChat';
import styles from './MeetingDetailModal.module.css';

interface MeetingDetailModalProps {
  meeting: MeetingSummary;
  segments: MeetingSegment[];
  segmentsLoading: boolean;
  segmentsError: string | null;
  messages: ChatMessage[];
  draft: string;
  asking: boolean;
  steps: string[];
  onClose: () => void;
  onDraftChange: (value: string) => void;
  onSend: () => void;
}

export function MeetingDetailModal({
  meeting,
  segments,
  segmentsLoading,
  segmentsError,
  messages,
  draft,
  asking,
  steps,
  onClose,
  onDraftChange,
  onSend,
}: MeetingDetailModalProps) {
  const [mode, setMode] = useState<'timeline' | 'transcript'>('timeline');
  const date = formatMeetingDate(meeting.meeting_date);
  const duration = `${Math.floor(meeting.duration_seconds / 60)}m ${meeting.duration_seconds % 60}s`;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerInfo}>
            <div className={styles.headerMeta}>
              <span className={styles.title}>{meeting.title}</span>
              <span className={styles.dateInfo}>{date} · {duration}</span>
            </div>
            <div className={styles.participants}>
              {meeting.participants.join(', ') || 'No participants'}
            </div>
            <div className={styles.summary}>{meeting.simple_summary}</div>
            {meeting.keywords.length > 0 && (
              <div className={styles.keywords}>
                {meeting.keywords.map((keyword) => (
                  <span key={keyword} className={styles.keyword}>{keyword}</span>
                ))}
              </div>
            )}
          </div>
          <button className={styles.closeBtn} onClick={onClose}>
            ×
          </button>
        </div>

        {/* Body */}
        <div className={styles.body}>
          {/* Left: Timeline / Transcript */}
          <div className={styles.leftPanel}>
            <div className={styles.leftHeader}>
              <div className={styles.modeLabel}>
                {mode === 'timeline' ? 'MEETING TIMELINE' : 'MEETING TRANSCRIPT'}
              </div>
              <button
                className={styles.hint}
                onClick={() => setMode(mode === 'timeline' ? 'transcript' : 'timeline')}
                style={{ cursor: 'pointer', background: 'none', border: 'none' }}
              >
                Switch to {mode === 'timeline' ? 'transcript' : 'timeline'} view
              </button>
            </div>
            <div className={styles.leftBody}>
              {segmentsLoading && <p className={styles.hint}>Loading transcript…</p>}
              {segmentsError && <p className={styles.hint}>{segmentsError}</p>}
              {!segmentsLoading && !segmentsError && (
                mode === 'timeline' ? (
                  <MeetingTimeline segments={segments} />
                ) : (
                  <MeetingTranscript segments={segments} />
                )
              )}
            </div>
          </div>

          {/* Right: Chat */}
          <DetailChat
            messages={messages}
            draft={draft}
            asking={asking}
            steps={steps}
            onDraftChange={onDraftChange}
            onSend={onSend}
          />
        </div>
      </div>
    </div>
  );
}
