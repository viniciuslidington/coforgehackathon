'use client';

import { useState, useCallback } from 'react';
import type {
  CallTypeFilter,
  PriorityFilter,
  SortColumn,
  SortDirection,
} from '@/entities/meeting/model/types';

export function useCallFilters(hasPriority: boolean = false) {
  const [typeFilter, setTypeFilter] = useState<CallTypeFilter>('all');
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>('all');
  const [sortColumn, setSortColumn] = useState<SortColumn>(hasPriority ? 'priority' : 'date');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const [prevHasPriority, setPrevHasPriority] = useState(hasPriority);
  if (hasPriority !== prevHasPriority) {
    setPrevHasPriority(hasPriority);
    setSortColumn(hasPriority ? 'priority' : 'date');
    setSortDirection('desc');
  }

  const toggleSort = useCallback((column: SortColumn) => {
    setSortColumn((currentColumn) => {
      if (currentColumn === column) {
        setSortDirection((currentDir) => (currentDir === 'asc' ? 'desc' : 'asc'));
        return currentColumn;
      }
      setSortDirection('desc');
      return column;
    });
  }, []);

  const resetFilters = useCallback(() => {
    setTypeFilter('all');
    setPriorityFilter('all');
  }, []);

  return {
    typeFilter,
    setTypeFilter,
    priorityFilter,
    setPriorityFilter,
    sortColumn,
    sortDirection,
    setSortColumn,
    setSortDirection,
    toggleSort,
    resetFilters,
  } as const;
}
