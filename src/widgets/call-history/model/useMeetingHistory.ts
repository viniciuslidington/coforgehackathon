'use client';

import { useCallback, useEffect, useState } from 'react';
import type { MeetingPeriod, MeetingSummaryPage, SortKey } from '@/entities/meeting/model/types';
import { getMeetingSummaries, syncMeetings } from '@/shared/api/meetings';

/**
 * Owns the meetings query for the table.
 *
 * Lifted out of the CallHistory widget so the page can read the rows that are
 * actually on screen: the Quick Chat's "this page" scope needs the same list
 * the table renders, and pushing it upward from inside the widget would mean
 * a state-sync effect the lint rules forbid.
 */
export function useMeetingHistory(topics: string[], backendSort: SortKey) {
  const [period, setPeriod] = useState<MeetingPeriod>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [data, setData] = useState<MeetingSummaryPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const [previousTopics, setPreviousTopics] = useState(topics);
  if (topics !== previousTopics) {
    setPreviousTopics(topics);
    setPage(1);
    setLoading(true);
  }

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    getMeetingSummaries(period, page, pageSize, topics, backendSort, controller.signal)
      .then(result => {
        if (active) setData(result);
      })
      .catch((requestError: unknown) => {
        if (!active || (requestError instanceof DOMException && requestError.name === 'AbortError')) return;
        setError(requestError instanceof Error ? requestError.message : 'Could not load meetings.');
        setData(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [page, pageSize, period, topics, backendSort]);

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const selectPeriod = useCallback((value: MeetingPeriod) => {
    setLoading(true);
    setError(null);
    setPeriod(value);
    setPage(1);
  }, []);

  const selectPageSize = useCallback((value: number) => {
    setLoading(true);
    setError(null);
    setPageSize(value);
    setPage(1);
  }, []);

  const goToPage = useCallback((next: (current: number) => number) => {
    setLoading(true);
    setError(null);
    setPage(next);
  }, []);

  const sync = useCallback(async () => {
    if (loading || syncing) return;
    setSyncing(true);
    setError(null);
    try {
      await syncMeetings();
      setLoading(true);
      setPage(1);
      // Changing the page alone does not retrigger the request when already
      // on page one, so reload the current result explicitly after syncing.
      setData(await getMeetingSummaries(period, 1, pageSize, topics, backendSort));
    } catch (syncError: unknown) {
      setError(syncError instanceof Error ? syncError.message : 'Could not sync meetings.');
    } finally {
      setSyncing(false);
      setLoading(false);
    }
  }, [loading, syncing, period, pageSize, topics, backendSort]);

  return {
    items: data?.items ?? [],
    total,
    totalPages,
    period,
    page,
    pageSize,
    loading,
    error,
    syncing,
    selectPeriod,
    selectPageSize,
    goToPage,
    sync,
  } as const;
}
