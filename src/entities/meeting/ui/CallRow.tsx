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

/** The snippet with every occurrence of any of the terms wrapped in <mark>. */
function highlighted(text: string, terms: string[]) {
  const needles = terms.map(term => term.trim().toLowerCase()).filter(Boolean);
  if (!needles.length) return text;
  const parts: ReactNode[] = [];
  const lower = text.toLowerCase();
  let from = 0;
  while (from < text.length) {
    // The earliest next occurrence of any term, longest first on a tie.
    let at = -1;
    let length = 0;
    for (const needle of needles) {
      const found = lower.indexOf(needle, from);
      if (found !== -1 && (at === -1 || found < at || (found === at && needle.length > length))) {
        at = found;
        length = needle.length;
      }
    }
    if (at === -1) break;
    if (at > from) parts.push(text.slice(from, at));
    parts.push(<mark key={at}>{text.slice(at, at + length)}</mark>);
    from = at + length;
  }
  if (from < text.length) parts.push(text.slice(from));
  return parts;
}

/** The parts of a composite topic ("Fed & Rates"), matching the backend's split. */
function topicTerms(topic: string): string[] {
  const parts = topic.split(/\s*(?:&|,|\/|\band\b)\s*/i).filter(part => part.length >= 2);
  return [topic, ...parts];
}

interface RowEvidence {
  seconds: number;
  snippet: string;
  label: string;
  terms: string[];
}

/**
 * The transcript moment worth showing under the summary, if any.
 *
 * A search match wins: it answers what the user just typed. Otherwise an
 * Urgent or High meeting shows the evidence for its topic score, since that
 * is what earned it the badge. A hit in the title or summary needs no line —
 * it is already on screen.
 */
function rowEvidence(meeting: MeetingSummary, showPriority: boolean, searchTerm: string): RowEvidence | null {
  const match = meeting.match;
  if (match) {
    const seconds = match.start ? parseClockSeconds(match.start) : null;
    if (!match.snippet || seconds === null) return null;
    return {
      seconds,
      snippet: match.snippet,
      label: match.source === 'transcript' ? 'Said at' : 'Related at',
      terms: [searchTerm],
    };
  }

  const reason = meeting.priority_reason;
  if (!showPriority || !reason || meeting.priority_tier === 'normal') return null;
  const seconds = reason.start ? parseClockSeconds(reason.start) : null;
  if (!reason.snippet || seconds === null) return null;
  return {
    seconds,
    snippet: reason.snippet,
    label: reason.kind === 'mentioned' ? `${reason.topic} at` : `About ${reason.topic} at`,
    terms: reason.kind === 'mentioned' ? topicTerms(reason.topic) : [],
  };
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

  const moment = rowEvidence(meeting, showPriority, highlight);

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
              {moment.label} {formatClock(moment.seconds)}
            </span>
            <span className={styles.matchSnippet}>{highlighted(moment.snippet, moment.terms)}</span>
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
          <PriorityBadge
            tier={meeting.priority_tier}
            score={meeting.priority_score}
            reason={meeting.priority_reason ?? null}
          />
        </div>
      )}
    </article>
  );
}
