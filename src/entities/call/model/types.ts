/* ── Call Entity — Type Definitions ─────────────────────────── */

export interface ChatMessage {
  role: 'user' | 'ai';
  text: string;
}

export type ContextLabel = 'Last 5 calls' | 'Last 2 hours' | 'Full shift';

export type KeyPointTone = 'urgent' | 'teal' | 'muted';

export interface KeyPoint {
  label: string;
  tone: KeyPointTone;
}

