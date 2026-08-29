import type { MeetingPeriod, MeetingSegment, MeetingSummary, MeetingSummaryPage, SortKey } from '@/entities/meeting/model/types';
import { API_BASE_URL } from './config';
import { readSseStream } from './sse';

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

export async function getMeetingById(meetingId: string, signal?: AbortSignal): Promise<MeetingSummary> {
  const response = await fetch(`${API_BASE_URL}/meeting-summaries/${meetingId}`, { signal });
  if (!response.ok) {
    throw new Error(`Could not load meeting (${response.status}).`);
  }
  return response.json() as Promise<MeetingSummary>;
}

export async function getMeetingTranscript(meetingId: string, signal?: AbortSignal): Promise<MeetingSegment[]> {
  const response = await fetch(`${API_BASE_URL}/meeting-summaries/${meetingId}/transcript`, { signal });
  if (!response.ok) {
    throw new Error(`Could not load transcript (${response.status}).`);
  }
  return response.json() as Promise<MeetingSegment[]>;
}

export type MeetingQuestionEvent =
  | { type: 'step'; label: string }
  | { type: 'answer'; text: string; caption_count: number }
  | { type: 'error'; detail: string };

export async function askMeetingQuestion(
  meetingId: string,
  question: string,
  sessionId: string,
  onEvent: (event: MeetingQuestionEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/meeting-summaries/${meetingId}/questions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, session_id: sessionId }),
    signal,
  });
  if (!response.ok) {
    throw new Error(`Could not get an answer (${response.status}).`);
  }
  await readSseStream<MeetingQuestionEvent>(
    response,
    onEvent,
    event => event.type === 'answer' || event.type === 'error',
    'The answer stream ended before returning a result.',
  );
}
