/**
 * A meeting scope is the set of meetings the Quick Chat agent may read.
 * The client picks a selection; the server resolves it to concrete meeting
 * ids plus a content fingerprint used as the briefing cache key.
 */
export type MeetingScope =
  | { kind: 'last_n'; count: number }
  | { kind: 'last_day' }
  /** Both bounds inclusive, YYYY-MM-DD. */
  | { kind: 'date_range'; date_from: string; date_to: string }
  | { kind: 'explicit'; meeting_ids: string[] };

export type ScopePreset = MeetingScope['kind'];

export interface ScopeResolution {
  fingerprint: string;
  meeting_ids: string[];
  meeting_count: number;
  range_start: string | null;
  range_end: string | null;
  resolved_at: string;
  truncated: boolean;
  missing_meeting_ids: string[];
}

export interface ReferencedMeeting {
  meeting_id: string;
  title: string;
  meeting_date: string;
}

export type KeyPointTone = 'urgent' | 'teal' | 'muted';

export interface BriefingKeyPoint {
  text: string;
  tone: KeyPointTone;
  meeting_id: string | null;
}

export interface Briefing {
  /** Three paragraphs, separated by a blank line. */
  summary: string;
  key_points: BriefingKeyPoint[];
  referenced_meetings: ReferencedMeeting[];
  scope: ScopeResolution;
  cached: boolean;
  truncated: boolean;
  created_at: string;
}

/** Above this many meetings, generating a briefing gets noticeably slower. */
export const SCOPE_WARNING_THRESHOLD = 15;
