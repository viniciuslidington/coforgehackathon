export type MeetingPeriod = 'day' | 'week' | '30d' | 'all';

export interface MeetingSummary {
  meeting_id: string;
  title: string;
  meeting_date: string;
  participants: string[];
  simple_summary: string;
  keywords: string[];
  duration_seconds: number;
  refreshed_at: string;
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
