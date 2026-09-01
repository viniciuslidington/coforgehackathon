import { Fragment, type ReactNode } from 'react';
import type { ReferencedMeeting } from '@/entities/meeting/model/scope';
import { renderInline, type InlineRule } from '@/shared/lib/richText';
import { formatClock, parseClockSeconds } from './transcriptTime';

/**
 * The agent writes `[[meeting:<id>]]` wherever it names a meeting, and the
 * server strips any id outside the current scope before sending. Splitting
 * on that marker turns those references into clickable titles without
 * pulling in a markdown renderer.
 */
/**
 * Matches the citation forms the model actually produces: with or without the
 * `meeting:` prefix, and one or several comma-separated ids per marker. The
 * server normalizes these, but briefings cached before it learned to may
 * still carry the looser shapes.
 */
const MARKER = /\[\[\s*(?:meeting\s*:)?\s*([^[\]\n]+?)\s*\]\]/g;

/**
 * How many meetings to link at one citation point. Mirrors the server's cap,
 * which briefings cached before that cap existed did not go through.
 */
const MAX_INLINE_CITATIONS = 3;

/** Ids inside one marker, in order. */
function idsInMarker(body: string): string[] {
  return body.split(',').map(part => part.trim().replace(/^meeting:\s*/, '')).filter(Boolean);
}

/**
 * Removes marker syntax from a string.
 *
 * For contexts that are already a single control — a key-point chip — where a
 * nested link would be invalid markup. Also covers briefings cached before
 * the server learned to strip markers out of bullet text.
 */
export function stripMeetingMarkers(text: string): string {
  return text.replace(MARKER, '').replace(/\s{2,}/g, ' ').trim().replace(/[,;–-]$/, '').trim();
}

/** The first meeting id mentioned in a string, if any. */
export function firstMeetingId(text: string): string | null {
  MARKER.lastIndex = 0;
  const body = MARKER.exec(text)?.[1];
  return body ? (idsInMarker(body)[0] ?? null) : null;
}

/**
 * A citation rule for the shared inline scanner, so meeting links can be
 * rendered in the same pass as Markdown rather than in a competing one.
 *
 * Holds the run counter that caps adjacent citations, so build a fresh rule
 * per render rather than memoizing one.
 */
export function meetingMarkerRule(
  meetings: ReferencedMeeting[],
  onOpen: (meetingId: string) => void,
  linkClassName?: string,
): InlineRule {
  const byId = new Map(meetings.map(meeting => [meeting.meeting_id, meeting]));
  // Links emitted in the current unbroken run of citations. The model chains
  // markers as well as grouping them, so the cap has to span adjacent
  // markers, not just the ids inside one.
  let used = 0;

  return {
    // Its own instance: `lastIndex` is driven by the scanner, and the module
    // regex above is shared with the two helpers.
    pattern: new RegExp(MARKER.source, 'g'),
    onText: () => {
      used = 0;
    },
    render: (match, key) => {
      // One marker can name several meetings; render each as its own link.
      const resolved = idsInMarker(match[1])
        .map(id => byId.get(id))
        .filter((meeting): meeting is ReferencedMeeting => Boolean(meeting));

      if (resolved.length === 0) {
        used = 0;
        // Defence in depth — the server already dropped unresolvable ids.
        // Consumed rather than replaced: a marker is a citation, not a noun.
        // Bracketed text that never claimed to be a citation is disclaimed
        // instead, rather than rewriting prose matched by accident.
        return /meeting/i.test(match[0]) ? '' : null;
      }

      const links: ReactNode[] = [];
      for (const meeting of resolved) {
        if (used >= MAX_INLINE_CITATIONS) break;
        // Without a separator, chained titles would run together as one word.
        if (used > 0) links.push(', ');
        used += 1;
        links.push(
          // A button, not a link: this opens a modal rather than navigating.
          <button
            key={`${key}-${meeting.meeting_id}`}
            type="button"
            className={linkClassName}
            onClick={() => onOpen(meeting.meeting_id)}
          >
            {meeting.title}
          </button>,
        );
      }
      return <Fragment key={key}>{links}</Fragment>;
    },
  };
}

/**
 * A citation that names both a meeting and a moment inside it:
 * `[[meeting:<id>@<start>-<end>]]`.
 *
 * Quick Chat needs this because one answer spans many meetings, so a bare
 * timestamp there cannot say which transcript to open. The server has already
 * checked the moment against that meeting's real cues, so anything arriving
 * here is safe to link.
 *
 * Must be ordered BEFORE `meetingMarkerRule`: both patterns match this form at
 * the same index, and the scanner breaks ties by array order. Behind it, the
 * plain rule would claim the match, fail to resolve the `@` suffix as an id,
 * and delete the citation.
 */
const TIMED_MARKER = /\[\[\s*meeting\s*:\s*([^[\]\n@]+?)\s*@\s*([^[\]\n]+?)\s*\]\]/g;
const RANGE = /^(.+?)\s*[–—-]\s*(.+)$/;

export function meetingTimeRule(
  meetings: ReferencedMeeting[],
  onOpenAt: (meetingId: string, fromSeconds: number | null, toSeconds: number | null) => void,
  linkClassName?: string,
): InlineRule {
  const byId = new Map(meetings.map(meeting => [meeting.meeting_id, meeting]));

  return {
    pattern: new RegExp(TIMED_MARKER.source, 'g'),
    render: (match, key) => {
      const meeting = byId.get(match[1]);
      // Consumed, not shown: an unresolvable citation is not prose.
      if (!meeting) return '';

      const parts = RANGE.exec(match[2]);
      const from = parseClockSeconds(parts ? parts[1] : match[2]);
      const to = parts ? parseClockSeconds(parts[2]) : null;

      // The meeting still opens even if the moment is unreadable.
      const label = from === null
        ? meeting.title
        : `${meeting.title} ${formatClock(from)}${to === null ? '' : `–${formatClock(to)}`}`;

      return (
        <button
          key={key}
          type="button"
          className={linkClassName}
          title={from === null ? 'Open this meeting' : 'Open this meeting at this moment'}
          onClick={() => onOpenAt(meeting.meeting_id, from, to)}
        >
          {label}
        </button>
      );
    },
  };
}

/**
 * Inline-only rendering of meeting citations, with no Markdown.
 *
 * Kept for callers that own their own block structure and want the text
 * otherwise untouched.
 */
export function renderWithMeetingLinks(
  text: string,
  meetings: ReferencedMeeting[],
  onOpen: (meetingId: string) => void,
  linkClassName?: string,
): ReactNode[] {
  return renderInline(text, [meetingMarkerRule(meetings, onOpen, linkClassName)], 'ml');
}
