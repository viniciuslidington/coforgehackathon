import type { Briefing, MeetingScope, ReferencedMeeting, ScopeResolution } from '@/entities/meeting/model/scope';
import { API_BASE_URL } from './config';
import { readSseStream } from './sse';

const JSON_HEADERS = { 'Content-Type': 'application/json' };

export interface BriefingLookup {
  scope: ScopeResolution;
  /** null when no briefing has been generated for this scope yet. */
  briefing: Briefing | null;
}

/**
 * Resolves a scope and returns its cached briefing in one round trip.
 * Never triggers generation, so it is safe to call on every scope change.
 */
export async function lookupBriefing(scope: MeetingScope, signal?: AbortSignal): Promise<BriefingLookup> {
  const response = await fetch(`${API_BASE_URL}/quick-chat/briefings/lookup`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ scope }),
    signal,
  });
  if (!response.ok) {
    throw new Error(`Could not resolve the meeting scope (${response.status}).`);
  }
  return response.json() as Promise<BriefingLookup>;
}

export type BriefingStreamEvent =
  | { type: 'step'; label: string }
  | { type: 'briefing'; briefing: Briefing }
  | { type: 'error'; detail: string };

export async function generateBriefing(
  scope: MeetingScope,
  onEvent: (event: BriefingStreamEvent) => void,
  signal?: AbortSignal,
  force = false,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/quick-chat/briefings`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ scope, force }),
    signal,
  });
  if (!response.ok) {
    throw new Error(`Could not generate a briefing (${response.status}).`);
  }
  await readSseStream<BriefingStreamEvent>(
    response,
    onEvent,
    event => event.type === 'briefing' || event.type === 'error',
    'The briefing stream ended before returning a result.',
  );
}

export type QuickChatEvent =
  | { type: 'step'; label: string }
  | { type: 'answer'; text: string; referenced_meetings: ReferencedMeeting[]; meeting_count: number }
  | { type: 'error'; detail: string };

export async function askQuickChat(
  question: string,
  sessionId: string,
  scope: MeetingScope,
  onEvent: (event: QuickChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/quick-chat/questions`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ question, session_id: sessionId, scope }),
    signal,
  });
  if (!response.ok) {
    throw new Error(`Could not get an answer (${response.status}).`);
  }
  await readSseStream<QuickChatEvent>(
    response,
    onEvent,
    event => event.type === 'answer' || event.type === 'error',
    'The answer stream ended before returning a result.',
  );
}
