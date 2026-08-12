/**
 * Design tokens — Shift Briefing
 * Extracted from the original Claude Design Component.
 */

/* ── Palette ────────────────────────────────────────────────── */

export const colors = {
  /* Brand */
  teal:        '#016a71',
  tealLight:   '#3fb6ba',
  tealPale:    '#78c9cb',
  tealBg:      '#1f2726',
  tealBorder:  '#24403f',
  tealHover:   '#068189',
  tealBorderL: '#0a8b93',
  tealText:    '#eafcfc',
  tealGlow:    '#e8fbfb',

  /* Urgent / Error */
  urgent:        '#e2603f',
  urgentBg:      '#2a1d1a',
  urgentBorder:  '#4a2a22',

  /* Warning / High */
  high: '#d8a24a',

  /* Backgrounds */
  bg0: '#171615',
  bg1: '#131211',
  bg2: '#1a1917',
  bg3: '#1c1b19',
  bg4: '#1e1d1b',
  bg5: '#1f1e1c',
  bg6: '#201f1c',
  bg7: '#221f1d',
  bg8: '#232120',
  bg9: '#242220',
  bgUrgentRow: '#1e1b19',

  /* Borders */
  border0: '#232120',
  border1: '#262421',
  border2: '#292724',
  border3: '#2b2926',
  border4: '#302e2b',
  border5: '#35322e',
  border6: '#3a3733',
  border7: '#4a4642',

  /* Text */
  textPrimary:   '#f2efea',
  textSecondary: '#d8d3cb',
  textTertiary:  '#c9c3ba',
  textMuted:     '#a8a29a',
  textDim:       '#8f8a81',
  textDimmer:    '#7f7a72',
  textDimmest:   '#6f6a63',
  textGhost:     '#5c5852',

  /* Overlay */
  overlay: 'rgba(10,9,9,0.72)',

  /* Selection */
  selection:     '#016a71',
  selectionText: '#ffffff',
} as const;

/* ── Typography ────────────────────────────────────────────── */

export const fonts = {
  sans:  "'Inter', Helvetica, Arial, sans-serif",
  mono:  "'JetBrains Mono', monospace",
} as const;

/* ── Spacing ───────────────────────────────────────────────── */

export const radius = {
  sm:  '6px',
  md:  '8px',
  lg:  '10px',
  xl:  '12px',
  xxl: '14px',
  pill: '999px',
  modal: '16px',
} as const;

/* ── Z-Index ───────────────────────────────────────────────── */

export const zIndex = {
  modal: 50,
} as const;

/* ── Sidebar ───────────────────────────────────────────────── */

export const sidebar = {
  width: 68,
} as const;
