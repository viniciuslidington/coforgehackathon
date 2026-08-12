'use client';

import type { Call } from '@/entities/call/model/types';
import type { ChatMessage } from '@/entities/call/model/types';
import { tierColor, tierLabel } from '@/entities/call/lib/helpers';
import { CallTimeline } from './CallTimeline';
import { CallTranscript } from './CallTranscript';
import { DetailChat } from './DetailChat';
import styles from './CallDetailModal.module.css';

interface CallDetailModalProps {
  call: Call;
  messages: ChatMessage[];
  draft: string;
  rangeText: string | null;
  isInRange: (index: number) => boolean;
  onPickSegment: (index: number) => void;
  onClose: () => void;
  onDraftChange: (value: string) => void;
  onSend: () => void;
  onClearRange: () => void;
  mode?: 'timeline' | 'transcript';
}

export function CallDetailModal({
  call,
  messages,
  draft,
  rangeText,
  isInRange,
  onPickSegment,
  onClose,
  onDraftChange,
  onSend,
  onClearRange,
  mode = 'timeline',
}: CallDetailModalProps) {
  const color = tierColor(call.tier);
  const label = tierLabel(call.tier);
  const highMentions = call.mentions >= 3;

  const priorityBg = call.tier === 'urgent' ? 'var(--urgent-bg)' : '#22201d';
  const priorityFg = call.tier === 'normal' ? 'var(--text-muted)' : color;
  const priorityBorder = call.tier === 'urgent' ? 'var(--urgent-border)' : 'var(--border-3)';

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerInfo}>
            <div className={styles.headerMeta}>
              <span
                className={styles.cp}
                style={{ color: highMentions ? 'var(--urgent)' : 'var(--text-primary)' }}
              >
                {call.cp}
              </span>
              <span className={styles.channel}>{call.channel}</span>
              <span className={styles.timeInfo}>{call.time} · {call.dur}</span>
              <span
                className={styles.priorityPill}
                style={{
                  background: priorityBg,
                  color: priorityFg,
                  borderColor: priorityBorder,
                }}
              >
                {label} · named {call.mentions}×
              </span>
            </div>
            <div className={styles.summary}>{call.summary}</div>
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
                {mode === 'timeline' ? 'CALL TIMELINE · NO AUDIO' : 'MOCK TRANSCRIPT'}
              </div>
              <div className={styles.hint}>
                Click a moment, then a second to set a range
              </div>
            </div>
            <div className={styles.leftBody}>
              {mode === 'timeline' ? (
                <CallTimeline
                  segments={call.segs}
                  isInRange={isInRange}
                  onPick={onPickSegment}
                />
              ) : (
                <CallTranscript
                  segments={call.segs}
                  isInRange={isInRange}
                  onPick={onPickSegment}
                />
              )}
            </div>
          </div>

          {/* Right: Chat */}
          <DetailChat
            messages={messages}
            draft={draft}
            rangeText={rangeText}
            onDraftChange={onDraftChange}
            onSend={onSend}
            onClearRange={onClearRange}
          />
        </div>
      </div>
    </div>
  );
}
