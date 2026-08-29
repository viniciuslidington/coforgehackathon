'use client';

import type { ScopePreset, ScopeResolution } from '@/entities/meeting/model/scope';
import { SCOPE_WARNING_THRESHOLD } from '@/entities/meeting/model/scope';
import { formatMeetingDate } from '@/entities/meeting/lib/helpers';
import { SCOPE_PRESETS } from '../model/useMeetingScope';
import styles from './ScopeSelector.module.css';

interface ScopeSelectorProps {
  preset: ScopePreset;
  onSelectPreset: (preset: ScopePreset) => void;
  range: { from: string; to: string };
  onRangeFromChange: (value: string) => void;
  onRangeToChange: (value: string) => void;
  rangeIsComplete: boolean;
  resolution: ScopeResolution | null;
  loading: boolean;
}

function describeRange(resolution: ScopeResolution): string {
  const { range_start: start, range_end: end, meeting_count: count } = resolution;
  const meetings = `${count} ${count === 1 ? 'meeting' : 'meetings'}`;
  if (!start || !end) return meetings;
  const span = start === end
    ? formatMeetingDate(start)
    : `${formatMeetingDate(start)} – ${formatMeetingDate(end)}`;
  return `${span} · ${meetings}`;
}

export function ScopeSelector({
  preset,
  onSelectPreset,
  range,
  onRangeFromChange,
  onRangeToChange,
  rangeIsComplete,
  resolution,
  loading,
}: ScopeSelectorProps) {
  const rangeInverted = Boolean(range.from && range.to && range.from > range.to);

  return (
    <div className={styles.scope}>
      <div className={styles.pills} aria-label="Meeting scope">
        {SCOPE_PRESETS.map(({ kind, label }) => (
          <button
            key={kind}
            type="button"
            className={`${styles.pill} ${preset === kind ? styles.pillActive : ''}`}
            aria-pressed={preset === kind}
            onClick={() => onSelectPreset(kind)}
          >
            {label}
          </button>
        ))}
      </div>

      {preset === 'date_range' && (
        <div className={styles.rangeRow}>
          <label className={styles.rangeField}>
            <span>From</span>
            <input
              type="date"
              value={range.from}
              max={range.to || undefined}
              onChange={event => onRangeFromChange(event.target.value)}
            />
          </label>
          <label className={styles.rangeField}>
            <span>To</span>
            <input
              type="date"
              value={range.to}
              min={range.from || undefined}
              onChange={event => onRangeToChange(event.target.value)}
            />
          </label>
        </div>
      )}

      {/* The resolved dates matter: "Last day" follows the newest synced
          meeting, which is rarely today. */}
      <div className={styles.meta}>
        {preset === 'date_range' && !rangeIsComplete
          ? (rangeInverted ? 'Start date must come before the end date.' : 'Pick a start and end date.')
          : loading
            ? 'Resolving scope…'
            : resolution
              ? describeRange(resolution)
              : 'No meetings in scope.'}
      </div>

      {resolution && resolution.meeting_count > SCOPE_WARNING_THRESHOLD && (
        <div className={styles.warning} role="status">
          {resolution.meeting_count} meetings selected — briefings and answers may take longer.
        </div>
      )}
    </div>
  );
}
