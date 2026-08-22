export type MeetingPeriod = 'day' | 'week' | '30d' | 'all';

export interface MeetingSummary {
  meeting_id: string;
  title: string;
  meeting_date: string;
  participants: string[];
  simple_summary: string;
  keywords: string[];
  refreshed_at: string;
}

export interface MeetingSummaryPage {
  items: MeetingSummary[];
  total: number;
  page: number;
  page_size: number;
}
