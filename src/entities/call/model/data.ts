import type { Call, ContextLabel, KeyPoint, PeriodOption, SortOption } from './types';

/* ── Mock Call Data ────────────────────────────────────────── */

export const CALLS: Call[] = [
  {
    id: 1, time: '14:12', ago: 6, dur: '2m 41s',
    cp: 'CITI-FX', channel: 'EUR spot hoot', score: 96, tier: 'urgent', mentions: 5,
    summary: 'Second attempt to reach you on a EUR/USD 250m block; they are working an order into the fix and asked for your axe before 15:00.',
    flags: [{ label: 'Named you 5×', urgent: true }, { label: 'EUR fix', urgent: false }],
    segs: [
      { t: '14:12:04', sp: 'CITI-FX', tx: 'Renata, second time asking — are you around? We have a 250 in EURUSD to work into the fix.' },
      { t: '14:12:31', sp: 'CITI-FX', tx: 'Client is patient but wants an indication of your axe before 15:00 London.', flag: 'Deadline' },
      { t: '14:13:10', sp: 'DESK', tx: 'She stepped off, back shortly. Leave the level with me.' },
      { t: '14:13:48', sp: 'CITI-FX', tx: 'Mid at 1.0912, we can show 3 tenths either side on the full amount.' },
      { t: '14:14:22', sp: 'CITI-FX', tx: 'If she is not back by half past we will split it across two banks.', flag: 'Escalation' },
      { t: '14:14:45', sp: 'DESK', tx: 'Understood — passing it up now.' },
    ],
  },
  {
    id: 2, time: '13:58', ago: 20, dur: '1m 12s',
    cp: 'NOMURA-RT', channel: 'JGB hoot', score: 92, tier: 'urgent', mentions: 1,
    summary: 'Off-market bid on 10y JGB, 4bp through screen and repeated twice — flagged as an anomaly against the last 30 days of quoting behaviour.',
    flags: [{ label: 'Anomaly', urgent: true }, { label: 'JGB 10y', urgent: false }],
    segs: [
      { t: '13:58:02', sp: 'NOMURA-RT', tx: 'Ten year bid at 1.482, firm for 500.' },
      { t: '13:58:19', sp: 'SYSTEM', tx: 'Level is 4bp through screen and 3.1σ from this counterparty\'s 30-day quoting range.', flag: 'Anomaly' },
      { t: '13:58:40', sp: 'NOMURA-RT', tx: 'Repeat: 1.482 bid, we are good for size all afternoon.' },
      { t: '13:59:01', sp: 'DESK', tx: 'Noted, nothing done here yet.' },
    ],
  },
  {
    id: 3, time: '14:10', ago: 8, dur: '3m 06s',
    cp: 'INTERNAL', channel: 'Rates desk hoot', score: 74, tier: 'high', mentions: 2,
    summary: 'CPI whisper number circulating; desk head asked everyone to flatten 2s10s risk into the print and to stop showing size below 5y.',
    flags: [{ label: 'Risk-off', urgent: false }],
    segs: [
      { t: '14:10:11', sp: 'DESK-HEAD', tx: 'Whisper is running two tenths above consensus. Flatten 2s10s into the print.' },
      { t: '14:11:02', sp: 'DESK-HEAD', tx: 'Nobody shows size below the 5y until we see the number.', flag: 'Instruction' },
      { t: '14:12:20', sp: 'INTERNAL', tx: 'Renata is off desk — she has the biggest belly position, someone tell her.' },
      { t: '14:13:04', sp: 'DESK-HEAD', tx: 'Put it in her briefing.' },
    ],
  },
  {
    id: 4, time: '13:47', ago: 31, dur: '0m 48s',
    cp: 'JPM-CRED', channel: 'Credit hoot', score: 61, tier: 'high', mentions: 2,
    summary: 'Asked whether you still have the flagged auto-issuer basis on; wants a two-way in 100m by tomorrow open.',
    flags: [{ label: 'Your flag: auto basis', urgent: false }],
    segs: [
      { t: '13:47:09', sp: 'JPM-CRED', tx: 'Does Renata still run the auto issuer basis? We have interest in 100.' },
      { t: '13:47:33', sp: 'DESK', tx: 'She does. Two-way?' },
      { t: '13:47:50', sp: 'JPM-CRED', tx: 'Two-way, needs a level by tomorrow open.', flag: 'Deadline' },
    ],
  },
  {
    id: 5, time: '13:35', ago: 43, dur: '4m 22s',
    cp: 'BARC-RT', channel: 'Swaps hoot', score: 48, tier: 'normal', mentions: 0,
    summary: 'Routine colour on 5y swap spreads widening 1.5bp; no request and no action needed.',
    flags: [],
    segs: [
      { t: '13:35:00', sp: 'BARC-RT', tx: 'Routine colour on 5y swap spreads widening 1.5bp; no request and no action needed.' },
      { t: '13:35:30', sp: 'DESK', tx: 'Acknowledged, nothing actioned on our side.' },
    ],
  },
  {
    id: 6, time: '13:22', ago: 56, dur: '1m 55s',
    cp: 'GS-FX', channel: 'EUR spot hoot', score: 44, tier: 'normal', mentions: 1,
    summary: 'Mentioned your name once in passing while confirming yesterday\'s NZD trade settled correctly.',
    flags: [],
    segs: [
      { t: '13:22:00', sp: 'GS-FX', tx: 'Mentioned your name once in passing while confirming yesterday\'s NZD trade settled correctly.' },
      { t: '13:22:30', sp: 'DESK', tx: 'Acknowledged, nothing actioned on our side.' },
    ],
  },
  {
    id: 7, time: '13:04', ago: 74, dur: '2m 09s',
    cp: 'HSBC-EM', channel: 'EM hoot', score: 39, tier: 'normal', mentions: 0,
    summary: 'MXN liquidity thinning ahead of the local holiday; they will not quote size after 16:00.',
    flags: [{ label: 'EM liquidity', urgent: false }],
    segs: [
      { t: '13:04:00', sp: 'HSBC-EM', tx: 'MXN liquidity thinning ahead of the local holiday; they will not quote size after 16:00.' },
      { t: '13:04:30', sp: 'DESK', tx: 'Acknowledged, nothing actioned on our side.' },
    ],
  },
  {
    id: 8, time: '12:51', ago: 87, dur: '0m 37s',
    cp: 'UBS-RT', channel: 'JGB hoot', score: 31, tier: 'normal', mentions: 0,
    summary: 'Quick check that the JGB hoot line was audible after the morning outage. No content.',
    flags: [],
    segs: [
      { t: '12:51:00', sp: 'UBS-RT', tx: 'Quick check that the JGB hoot line was audible after the morning outage. No content.' },
      { t: '12:51:30', sp: 'DESK', tx: 'Acknowledged, nothing actioned on our side.' },
    ],
  },
  {
    id: 9, time: '12:30', ago: 108, dur: '5m 41s',
    cp: 'INTERNAL', channel: 'Rates desk hoot', score: 28, tier: 'normal', mentions: 0,
    summary: 'Morning position walk-through repeated for the late shift; nothing new versus the 09:00 version.',
    flags: [],
    segs: [
      { t: '12:30:00', sp: 'INTERNAL', tx: 'Morning position walk-through repeated for the late shift; nothing new versus the 09:00 version.' },
      { t: '12:30:30', sp: 'DESK', tx: 'Acknowledged, nothing actioned on our side.' },
    ],
  },
  {
    id: 10, time: '11:58', ago: 140, dur: '1m 30s',
    cp: 'MS-CRED', channel: 'Credit hoot', score: 22, tier: 'normal', mentions: 0,
    summary: 'Indicative levels on two utility names, both inside where we are marked.',
    flags: [],
    segs: [
      { t: '11:58:00', sp: 'MS-CRED', tx: 'Indicative levels on two utility names, both inside where we are marked.' },
      { t: '11:58:30', sp: 'DESK', tx: 'Acknowledged, nothing actioned on our side.' },
    ],
  },
  {
    id: 11, time: '11:20', ago: 178, dur: '2m 14s',
    cp: 'DB-RT', channel: 'Swaps hoot', score: 18, tier: 'normal', mentions: 0,
    summary: 'Housekeeping on last week\'s compression run; confirmations already matched.',
    flags: [],
    segs: [
      { t: '11:20:00', sp: 'DB-RT', tx: 'Housekeeping on last week\'s compression run; confirmations already matched.' },
      { t: '11:20:30', sp: 'DESK', tx: 'Acknowledged, nothing actioned on our side.' },
    ],
  },
];

/* ── Filter & Sort Options ────────────────────────────────── */

export const PERIODS: PeriodOption[] = [
  { label: '30m', minutes: 30 },
  { label: '2h', minutes: 120 },
  { label: 'Shift', minutes: 480 },
  { label: 'All', minutes: 99999 },
];

export const SORTS: SortOption[] = [
  { label: 'Priority', key: 'priority' },
  { label: 'Time', key: 'time' },
  { label: 'Mentions', key: 'mentions' },
];

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
