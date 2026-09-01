import type { ReactNode } from 'react';
import type { MeetingSegment } from '@/entities/meeting/model/types';
import type { InlineRule } from '@/shared/lib/richText';

/**
 * Resolving a chat citation like `[00:12:45.500]` to the transcript cue it
 * names.
 *
 * The agent reads the meeting as `[start–end] text` lines, so it cites raw VTT
 * times. Segments carry those verbatim in `start`/`end`; `t` is display only
 * and cannot be matched against — it has lost the milliseconds, and rounding
 * can push it a second past the cue it labels.
 */

const TIME = String.raw`(?:\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?`;
// En dash is what the transcript itself uses; em dash and hyphen are the
// model improvising.
const DASH = String.raw`\s*[–—-]\s*`;

/**
 * All three shapes the model produces, as one pattern with optional suffixes
 * rather than alternatives — JS alternation is leftmost-first, not longest, so
 * an alternation would match the lone form inside `[a]–[b]` and emit two
 * buttons where the citation meant one range.
 *
 * Group 1 is the seek target. Groups 2 and 3 are the range end, whichever side
 * of the bracket the model put it on.
 */
const TIMESTAMP = new RegExp(
  String.raw`\[\s*(${TIME})(?:${DASH}(${TIME}))?\s*\]` + String.raw`(?:${DASH}\[\s*(${TIME})\s*\])?`,
  'g',
);

/** Seconds from "M:SS", "H:MM:SS" or "HH:MM:SS.mmm". Null when unparseable. */
export function parseClockSeconds(raw: string): number | null {
  const parts = raw.trim().replace(',', '.').split(':');
  if (parts.length < 2 || parts.length > 3) return null;

  const numbers = parts.map(Number);
  if (numbers.some(value => !Number.isFinite(value))) return null;

  const [hours, minutes, seconds] = parts.length === 3 ? numbers : [0, ...numbers];
  return hours * 3600 + minutes * 60 + seconds;
}

/**
 * Elapsed seconds for display, matching the backend's `format_timestamp` so a
 * citation's label reads the same as the timeline entry it scrolls to.
 */
export function formatClock(seconds: number): string {
  const total = Math.round(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const padded = `${minutes.toString().padStart(hours ? 2 : 1, '0')}:${secs.toString().padStart(2, '0')}`;
  return hours ? `${hours}:${padded}` : padded;
}

/** Where a segment starts, preferring the exact cue bound over the display string. */
export function segmentStartSeconds(segment: MeetingSegment): number {
  return parseClockSeconds(segment.start ?? segment.t) ?? 0;
}

/**
 * The last segment starting at or before `seconds`, or null when the
 * transcript is empty.
 *
 * Deliberately not an equality test: a citation can land mid-cue, and when
 * `start` is missing the fallback to `t` is only accurate to the second.
 */
export function findSegmentAt(segments: MeetingSegment[], seconds: number): number | null {
  let found: number | null = null;
  for (let index = 0; index < segments.length; index += 1) {
    if (segmentStartSeconds(segments[index]) <= seconds) found = index;
    else break;
  }
  return found ?? (segments.length > 0 ? 0 : null);
}

/**
 * Every segment the cited range covers: the one containing the range start,
 * plus each one beginning before the range ends.
 */
export function segmentsInRange(
  segments: MeetingSegment[],
  fromSeconds: number,
  toSeconds: number | null,
): Set<number> {
  const first = findSegmentAt(segments, fromSeconds);
  if (first === null) return new Set();

  const covered = new Set<number>([first]);
  if (toSeconds === null) return covered;

  for (let index = first + 1; index < segments.length; index += 1) {
    if (segmentStartSeconds(segments[index]) > toSeconds) break;
    covered.add(index);
  }
  return covered;
}

/**
 * A citation rule for the shared inline scanner: turns a bracketed timestamp
 * into a control that jumps the transcript to that moment.
 *
 * The label is re-formatted to the transcript's own clock, so the button reads
 * like the entry it scrolls to rather than echoing raw VTT precision.
 */
export function timeRangeRule(
  onSeek: (fromSeconds: number, toSeconds: number | null) => void,
  className?: string,
): InlineRule {
  return {
    pattern: new RegExp(TIMESTAMP.source, 'g'),
    render: (match, key): ReactNode | null => {
      const from = parseClockSeconds(match[1]);
      // Bracketed text shaped like a time but not parseable is prose; leave it.
      if (from === null) return null;

      const to = parseClockSeconds(match[2] ?? match[3] ?? '');
      const label = to === null ? formatClock(from) : `${formatClock(from)}–${formatClock(to)}`;

      return (
        <button
          key={key}
          type="button"
          className={className}
          title="Jump to this moment"
          onClick={() => onSeek(from, to)}
        >
          {label}
        </button>
      );
    },
  };
}
