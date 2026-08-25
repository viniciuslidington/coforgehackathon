import type { MeetingPeriod, MeetingSegment, MeetingSummaryPage, SortKey } from '@/entities/meeting/model/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_MEETING_API_URL ?? 'http://localhost:8000';

export async function syncMeetings(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/sync-meetings`, { method: 'POST' });
  if (!response.ok) {
    throw new Error(`Could not sync meetings (${response.status}).`);
  }
}

export async function getMeetingSummaries(
  period: MeetingPeriod,
  page: number,
  pageSize: number,
  topics: string[] = [],
  sort: SortKey = 'priority',
  signal?: AbortSignal,
): Promise<MeetingSummaryPage> {
  const params = new URLSearchParams({ period, page: String(page), page_size: String(pageSize), sort });
  for (const topic of topics) {
    if (topic.trim()) params.append('topics', topic.trim());
  }
  const response = await fetch(`${API_BASE_URL}/meeting-summaries?${params}`, { signal });
  if (!response.ok) {
    throw new Error(`Could not load meetings (${response.status}).`);
  }
  return response.json() as Promise<MeetingSummaryPage>;
}

export async function getMeetingTranscript(meetingId: string, signal?: AbortSignal): Promise<MeetingSegment[]> {
  const response = await fetch(`${API_BASE_URL}/meeting-summaries/${meetingId}/transcript`, { signal });
  if (!response.ok) {
    throw new Error(`Could not load transcript (${response.status}).`);
  }
  return response.json() as Promise<MeetingSegment[]>;
}

export async function askMeetingQuestion(meetingId: string, question: string, signal?: AbortSignal): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/meeting-summaries/${meetingId}/questions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
    signal,
  });
  if (!response.ok) {
    throw new Error(`Could not get an answer (${response.status}).`);
  }
  const data = await response.json() as { result: string };
  return data.result;
}
