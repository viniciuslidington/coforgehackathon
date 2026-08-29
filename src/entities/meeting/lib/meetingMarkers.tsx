import type { ReactNode } from 'react';
import type { ReferencedMeeting } from '@/entities/meeting/model/scope';

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

export function renderWithMeetingLinks(
  text: string,
  meetings: ReferencedMeeting[],
  onOpen: (meetingId: string) => void,
  linkClassName?: string,
): ReactNode[] {
  const byId = new Map(meetings.map(meeting => [meeting.meeting_id, meeting]));
  const nodes: ReactNode[] = [];
  let cursor = 0;
  let match: RegExpExecArray | null;
  // Counts links in the current unbroken run of citations. The model chains
  // markers as well as grouping them, so the cap has to span adjacent
  // markers, not just the ids inside one. Reset by any intervening text.
  let runLength = 0;

  MARKER.lastIndex = 0;
  while ((match = MARKER.exec(text)) !== null) {
    if (match.index > cursor) {
      nodes.push(text.slice(cursor, match.index));
      runLength = 0;
    }

    // One marker can name several meetings; render each as its own link.
    const resolved = idsInMarker(match[1])
      .map(id => byId.get(id))
      .filter((meeting): meeting is ReferencedMeeting => Boolean(meeting));

    if (resolved.length > 0) {
      for (const meeting of resolved) {
        if (runLength >= MAX_INLINE_CITATIONS) break;
        // Without a separator, chained titles would run together as one word.
        if (runLength > 0) nodes.push(', ');
        runLength += 1;
        // A button, not a link: this opens a modal rather than navigating.
        nodes.push(
          <button
            key={`${match!.index}-${meeting.meeting_id}`}
            type="button"
            className={linkClassName}
            onClick={() => onOpen(meeting.meeting_id)}
          >
            {meeting.title}
          </button>,
        );
      }
    } else if (/meeting/i.test(match[0])) {
      // Defence in depth — the server already dropped unresolvable ids.
      // Removed, not replaced: a marker is a citation, not a noun.
      runLength = 0;
    } else {
      // Bracketed text that never claimed to be a citation: leave it be
      // rather than rewrite prose we may have matched by accident.
      nodes.push(match[0]);
      runLength = 0;
    }
    cursor = match.index + match[0].length;
  }

  if (cursor < text.length) {
    nodes.push(text.slice(cursor));
  }
  return nodes;
}
