'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { MeetingSummary } from '../model/types';
import { formatMeetingDate, getCallType } from '../lib/helpers';
import { formatClock, parseClockSeconds } from '../lib/transcriptTime';
import { PriorityBadge } from './PriorityBadge';
import styles from './CallRow.module.css';

interface CallRowProps {
  meeting: MeetingSummary;
  onOpen?: (meeting: MeetingSummary) => void;
  /** Opens the meeting scrolled to a moment, in seconds. */
  onOpenAt?: (meeting: MeetingSummary, seconds: number) => void;
  showPriority?: boolean;
  /** The active table search, marked inside a match snippet. */
  highlight?: string;
}

/** The snippet with every occurrence of the search term wrapped in <mark>. */
function highlighted(text: string, term: string) {
  const needle = term.trim().toLowerCase();
  if (!needle) return text;
  const parts: ReactNode[] = [];
  const lower = text.toLowerCase();
  let from = 0;
  for (let at = lower.indexOf(needle); at !== -1; at = lower.indexOf(needle, from)) {
    if (at > from) parts.push(text.slice(from, at));
    parts.push(<mark key={at}>{text.slice(at, at + needle.length)}</mark>);
    from = at + needle.length;
  }
  if (from < text.length) parts.push(text.slice(from));
  return parts;
}

export function CallRow({ meeting, onOpen, onOpenAt, showPriority = true, highlight = '' }: CallRowProps) {
  const date = formatMeetingDate(meeting.meeting_date);
  const duration = `${Math.floor(meeting.duration_seconds / 60)}m ${meeting.duration_seconds % 60}s`;
  const callType = getCallType(meeting);

  // The summary cell rests clipped to two lines and grows to the whole text
  // while that cell is hovered. `max-height` cannot animate to `auto`, so the
  // full height is measured and applied as an explicit pixel value.
  const clipRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLDivElement>(null);
  const collapsedHeightRef = useRef(0);
  const [expandedHeight, setExpandedHeight] = useState<number | null>(null);
  const [clipped, setClipped] = useState(false);

  useEffect(() => {
    const clip = clipRef.current;
    const text = textRef.current;
    if (!clip || !text) return;

    // Read the resting height from the stylesheet once, while the cell is
    // still collapsed, so the two-line limit stays defined in one place.
    if (!collapsedHeightRef.current) {
      collapsedHeightRef.current = parseFloat(getComputedStyle(clip).maxHeight) || 0;
    }

    // The inner text keeps its full height whether or not the clip box is
    // open, so this stays correct mid-animation.
    const measure = () =>
      setClipped(text.getBoundingClientRect().height > collapsedHeightRef.current + 1);

    measure();
    // Column widths follow the panel's container queries, so re-wrapping text
    // can make a summary start or stop overflowing without any state change.
    const observer = new ResizeObserver(measure);
    observer.observe(text);
    return () => observer.disconnect();
  }, [meeting.simple_summary]);

  // Only a transcript match needs explaining in the row: a hit in the title,
  // keywords or summary is already on screen.
  const match = meeting.match;
  const matchSeconds = match?.start ? parseClockSeconds(match.start) : null;
  const moment = match?.snippet && matchSeconds !== null
    ? { seconds: matchSeconds, snippet: match.snippet, said: match.source === 'transcript' }
    : null;

  const expandSummary = () => {
    const text = textRef.current;
    if (text && clipped) setExpandedHeight(text.getBoundingClientRect().height);
  };

  return (
    <article
      className={`${styles.row} ${showPriority ? '' : styles.noPriority}`}
      onClick={() => onOpen?.(meeting)}
      style={onOpen ? { cursor: 'pointer' } : undefined}
    >
      <div>
        <div className={styles.time}>{date}</div>
      </div>

      <div>
        <span className={styles.typeBadge} data-type={callType.type}>
          {callType.label}
        </span>
      </div>

      <div className={styles.duration}>{duration}</div>

      <div>
        <div className={styles.counterparty}>{meeting.title}</div>
        <div className={styles.channel}>{meeting.participants.join(', ') || 'No participants'}</div>
      </div>

      <div className={styles.participants}>{meeting.participants.join(', ') || 'No participants'}</div>

      <div
        className={styles.summaryCol}
        onMouseEnter={expandSummary}
        onMouseLeave={() => setExpandedHeight(null)}
      >
        <div
          ref={clipRef}
          className={styles.summaryClip}
          style={expandedHeight != null ? { maxHeight: expandedHeight } : undefined}
        >
          <div ref={textRef} className={styles.summaryText}>{meeting.simple_summary}</div>
          {clipped && (
            <span
              className={styles.summaryFade}
              data-hidden={expandedHeight != null ? 'true' : undefined}
              aria-hidden="true"
            />
          )}
        </div>
        {moment && (
          <button
            type="button"
            className={styles.match}
            onClick={event => {
              // The row itself opens the meeting at the top.
              event.stopPropagation();
              if (onOpenAt) onOpenAt(meeting, moment.seconds);
              else onOpen?.(meeting);
            }}
            title="Open the meeting at this moment"
          >
            <span className={styles.matchTime}>
              {moment.said ? 'Said at' : 'Related at'} {formatClock(moment.seconds)}
            </span>
            <span className={styles.matchSnippet}>{highlighted(moment.snippet, highlight)}</span>
          </button>
        )}
      </div>

      <div className={styles.keywords}>
        {meeting.keywords.length ? meeting.keywords.map((keyword) => (
          <span key={keyword} className={styles.keyword}>{keyword}</span>
        )) : <span className={styles.emptyKeyword}>No keywords yet</span>}
      </div>

      {showPriority && meeting.priority_tier && meeting.priority_score != null && (
        <div className={styles.priority}>
          <PriorityBadge tier={meeting.priority_tier} score={meeting.priority_score} />
        </div>
      )}
    </article>
  );
}
