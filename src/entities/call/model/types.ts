/* ── Call Entity — Type Definitions ─────────────────────────── */

export type Priority = 'urgent' | 'high' | 'normal';

export interface CallFlag {
  label: string;
  urgent: boolean;
}

export interface CallSegment {
  /** Timestamp string, e.g. "14:12:04" */
  t: string;
  /** Speaker identifier, e.g. "CITI-FX", "DESK", "SYSTEM" */
  sp: string;
  /** Transcript text */
  tx: string;
  /** Optional flag label, e.g. "Deadline", "Anomaly" */
  flag?: string;
}

export interface Call {
  id: number;
  /** Display time, e.g. "14:12" */
  time: string;
  /** Minutes ago from "now" */
  ago: number;
  /** Duration string, e.g. "2m 41s" */
  dur: string;
  /** Counterparty short name */
  cp: string;
  /** Channel name */
  channel: string;
  /** Priority score 0–100 */
  score: number;
  /** Priority tier */
  tier: Priority;
  /** Number of times the user was mentioned */
  mentions: number;
  /** AI-generated summary */
  summary: string;
  /** Flag badges */
  flags: CallFlag[];
  /** Conversation segments (timeline / transcript) */
  segs: CallSegment[];
}

export type SortKey = 'priority' | 'time' | 'mentions';

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

export interface PeriodOption {
  label: string;
  minutes: number;
}

export interface SortOption {
  label: string;
  key: SortKey;
}
