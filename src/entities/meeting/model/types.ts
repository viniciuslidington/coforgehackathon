import type { ReferencedMeeting } from './scope';

export type MeetingPeriod = 'day' | 'week' | '30d' | 'all';

export type Priority = 'urgent' | 'high' | 'normal';

export type SortKey = 'priority' | 'time';

export type CallTypeFilter = 'all' | 'hoot' | 'group';
export type PriorityFilter = 'all' | 'urgent' | 'high' | 'normal';
export type SortColumn = 'date' | 'type' | 'priority';
export type SortDirection = 'asc' | 'desc';

export interface MeetingSummary {
  meeting_id: string;
  title: string;
  meeting_date: string;
  participants: string[];
  simple_summary: string;
  keywords: string[];
  duration_seconds: number;
  refreshed_at: string;
  priority_score?: number | null;
  priority_tier?: Priority | null;
  call_type?: 'hoot' | 'group' | string | null;
}

export interface MeetingSummaryPage {
  items: MeetingSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface MeetingSegment {
  /**
   * Elapsed time for display, e.g. "12:45" — rounded to the second, and
   * without the hour under an hour. Lossy: use `start` to match a citation.
   */
  t: string;
  /** Speaker label, e.g. "CITI-FX", "Renata" */
  sp: string;
  /** Segment text */
  tx: string;
  /** Optional flag label, e.g. "Deadline" */
  flag?: string;
  /**
   * Raw VTT cue bounds, e.g. "00:12:45.500". These are the strings the chat
   * agent cites back, so they are what a citation resolves against. Optional
   * only to tolerate a server that predates them.
   */
  start?: string;
  end?: string;
}

export interface ChatMessage {
  role: 'user' | 'ai';
  text: string;
  /**
   * Meetings the agent cited in `text` via `[[meeting:<id>]]` markers.
   * Only the Quick Chat sets this; the per-meeting chat leaves it undefined.
   */
  meetings?: ReferencedMeeting[];
}
