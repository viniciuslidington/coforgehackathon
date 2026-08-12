'use client';

import { useState, useCallback } from 'react';
import type { SortKey } from '@/entities/call/model/types';

const DEFAULT_PERIOD = 480; // Shift
const DEFAULT_SORT: SortKey = 'priority';

export function useCallFilters() {
  const [period, setPeriod] = useState(DEFAULT_PERIOD);
  const [sort, setSort] = useState<SortKey>(DEFAULT_SORT);

  const selectPeriod = useCallback((minutes: number) => {
    setPeriod(minutes);
  }, []);

  const selectSort = useCallback((key: SortKey) => {
    setSort(key);
  }, []);

  return { period, sort, selectPeriod, selectSort } as const;
}
