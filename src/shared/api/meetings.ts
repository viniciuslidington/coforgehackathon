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
  if (!response.body) {
    throw new Error('The answer stream is unavailable in this browser.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let terminalEventReceived = false;

  const emitFrames = (flush = false) => {
    buffer = buffer.replaceAll('\r\n', '\n');
    const frames = buffer.split('\n\n');
    buffer = flush ? '' : (frames.pop() ?? '');
    for (const frame of frames) {
      const payload = frame
        .split('\n')
        .filter(line => line.startsWith('data:'))
        .map(line => line.slice(5).trimStart())
        .join('\n');
      if (!payload) continue;
      const event = JSON.parse(payload) as MeetingQuestionEvent;
      if (event.type === 'answer' || event.type === 'error') terminalEventReceived = true;
      onEvent(event);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    emitFrames(done);
    if (done) break;
  }
  if (!terminalEventReceived) {
    throw new Error('The answer stream ended before returning a result.');
  }
}
