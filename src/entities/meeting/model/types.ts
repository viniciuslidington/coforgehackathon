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
  /** Timestamp string, e.g. "00:01:20" */
  t: string;
  /** Speaker label, e.g. "CITI-FX", "Renata" */
  sp: string;
  /** Segment text */
  tx: string;
  /** Optional flag label, e.g. "Deadline" */
  flag?: string;
}

export interface ChatMessage {
  role: 'user' | 'ai';
  text: string;
}
