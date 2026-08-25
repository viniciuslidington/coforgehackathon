import type { ContextLabel, KeyPoint } from './types';

export const CONTEXTS: ContextLabel[] = [
  'Last 5 calls',
  'Last 2 hours',
  'Full shift',
];

/* ── AI Briefing Responses ────────────────────────────────── */

export const BRIEF: Record<ContextLabel, string> = {
  'Last 5 calls':
    'Two things need you now. CITI-FX has called twice about a EUR/USD 250m block and needs your axe before 15:00 London. Nomura showed an off-market 10y JGB bid at 13:58, 4bp through screen and 3.1σ from their own 30-day range.\n\nDesk head also flattened 2s10s into the CPI print and asked for no size below the 5y — you hold the largest belly position on the desk.',
  'Last 2 hours':
    'Across 8 calls: one unanswered counterparty (CITI-FX, twice), one pricing anomaly (NOMURA-RT on 10y JGB), one internal instruction (flatten 2s10s, no size below 5y).\n\nEverything else was colour: 5y swap spreads +1.5bp, MXN liquidity thinning before the local holiday, and a settlement confirmation from GS-FX.',
  'Full shift':
    'Eleven calls since 11:20. Signal is concentrated in the last 25 minutes — before 13:35 it was housekeeping, compression confirms and repeated position walk-throughs.\n\nOpen items on you: CITI-FX EUR/USD axe (15:00), JPM-CRED two-way on the auto issuer basis (tomorrow open), and the desk-wide 2s10s flattening instruction.',
};

/* ── Key Points Per Context ───────────────────────────────── */

export const KEYPOINTS: Record<ContextLabel, KeyPoint[]> = {
  'Last 5 calls': [
    { label: 'CITI-FX unanswered ×2', tone: 'urgent' },
    { label: 'JGB bid 4bp through', tone: 'urgent' },
    { label: 'Flatten 2s10s', tone: 'teal' },
    { label: 'EUR fix 15:00', tone: 'teal' },
    { label: 'No size < 5y', tone: 'muted' },
  ],
  'Last 2 hours': [
    { label: 'CITI-FX unanswered ×2', tone: 'urgent' },
    { label: 'JGB anomaly 3.1σ', tone: 'urgent' },
    { label: 'Flatten 2s10s', tone: 'teal' },
    { label: 'MXN thinning', tone: 'muted' },
    { label: '5y spreads +1.5bp', tone: 'muted' },
  ],
  'Full shift': [
    { label: 'CITI-FX unanswered ×2', tone: 'urgent' },
    { label: 'JGB anomaly 3.1σ', tone: 'urgent' },
    { label: 'Auto basis two-way', tone: 'teal' },
    { label: 'EUR fix 15:00', tone: 'teal' },
    { label: 'Compression confirmed', tone: 'muted' },
    { label: 'Hoot outage cleared', tone: 'muted' },
  ],
};
