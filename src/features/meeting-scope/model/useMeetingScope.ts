'use client';

import { useCallback, useMemo, useState } from 'react';
import type { MeetingScope, ScopePreset } from '@/entities/meeting/model/scope';

export const LAST_N_COUNT = 5;

export const SCOPE_PRESETS: { kind: ScopePreset; label: string }[] = [
  { kind: 'last_n', label: `Last ${LAST_N_COUNT}` },
  { kind: 'last_day', label: 'Last day' },
  { kind: 'date_range', label: 'Date range' },
  { kind: 'explicit', label: 'This page' },
];

interface DateRange {
  from: string;
  to: string;
}

/**
 * Owns which scope preset is selected and turns it into the `MeetingScope`
 * sent to the server.
 *
 * `visibleMeetingIds` comes from the meetings table, so the "this page"
 * preset always matches exactly what the user can see — including its
 * pagination, filters, and sort.
 */
export function useMeetingScope(visibleMeetingIds: string[]) {
  const [preset, setPreset] = useState<ScopePreset>('last_n');
  const [range, setRange] = useState<DateRange>({ from: '', to: '' });

  const rangeIsComplete = Boolean(range.from && range.to && range.from <= range.to);
  // Join the ids so the memo below depends on the contents, not the array
  // identity — the table hands us a freshly built array on every render.
  const visibleKey = visibleMeetingIds.join(',');

  const scope = useMemo<MeetingScope | null>(() => {
    switch (preset) {
      case 'last_n':
        return { kind: 'last_n', count: LAST_N_COUNT };
      case 'last_day':
        return { kind: 'last_day' };
      case 'date_range':
        // Incomplete or inverted range: hold off rather than ask the server
        // to resolve something it will reject.
        return rangeIsComplete ? { kind: 'date_range', date_from: range.from, date_to: range.to } : null;
      case 'explicit':
        return visibleKey ? { kind: 'explicit', meeting_ids: visibleKey.split(',') } : null;
    }
  }, [preset, rangeIsComplete, range.from, range.to, visibleKey]);

  const selectPreset = useCallback((next: ScopePreset) => setPreset(next), []);
  const setRangeFrom = useCallback((from: string) => setRange(current => ({ ...current, from })), []);
  const setRangeTo = useCallback((to: string) => setRange(current => ({ ...current, to })), []);

  return {
    preset,
    selectPreset,
    range,
    setRangeFrom,
    setRangeTo,
    rangeIsComplete,
    scope,
  } as const;
}
