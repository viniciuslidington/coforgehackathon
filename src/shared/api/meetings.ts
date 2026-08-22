import type { MeetingPeriod, MeetingSummaryPage } from '@/entities/meeting/model/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_MEETING_API_URL ?? 'http://localhost:8000';

export async function getMeetingSummaries(
  period: MeetingPeriod,
  page: number,
  pageSize: number,
  signal?: AbortSignal,
): Promise<MeetingSummaryPage> {
  const params = new URLSearchParams({ period, page: String(page), page_size: String(pageSize) });
  const response = await fetch(`${API_BASE_URL}/meeting-summaries?${params}`, { signal });
  if (!response.ok) {
    throw new Error(`Could not load meetings (${response.status}).`);
  }
  return response.json() as Promise<MeetingSummaryPage>;
}
