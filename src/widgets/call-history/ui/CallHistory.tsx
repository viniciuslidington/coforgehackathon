'use client';

import { useEffect, useState } from 'react';
import type { MeetingPeriod, MeetingSummaryPage } from '@/entities/meeting/model/types';
import { getMeetingSummaries } from '@/shared/api/meetings';
import { CallRow } from '@/entities/call/ui/CallRow';
import styles from './CallHistory.module.css';

const PERIODS: { label: string; value: MeetingPeriod }[] = [
  { label: 'Today', value: 'day' },
  { label: '7 days', value: 'week' },
  { label: '30 days', value: '30d' },
  { label: 'All', value: 'all' },
];
const PAGE_SIZES = [15, 30, 50, 100];

export function CallHistory() {
  const [period, setPeriod] = useState<MeetingPeriod>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [data, setData] = useState<MeetingSummaryPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    getMeetingSummaries(period, page, pageSize, controller.signal)
      .then((result) => {
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
  }, [page, pageSize, period]);

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const selectPeriod = (value: MeetingPeriod) => {
    setLoading(true);
    setError(null);
    setPeriod(value);
    setPage(1);
  };
  const selectPageSize = (value: number) => {
    setLoading(true);
    setError(null);
    setPageSize(value);
    setPage(1);
  };

  return (
    <section className={styles.panel} aria-label="Meeting summaries">
      <div className={styles.toolbar}>
        <div className={styles.titleGroup}>
          <div className={styles.title}>Meeting summaries</div>
          <div className={styles.count}>{loading ? 'Loading…' : `${total} meetings`}</div>
        </div>
        <div className={styles.controls}>
          <div className={styles.periods} aria-label="Date range">
            {PERIODS.map(({ label, value }) => (
              <button key={value} className={`${styles.period} ${period === value ? styles.active : ''}`} onClick={() => selectPeriod(value)}>
                {label}
              </button>
            ))}
          </div>
          <label className={styles.pageSize}>
            Per page
            <select value={pageSize} onChange={(event) => selectPageSize(Number(event.target.value))}>
              {PAGE_SIZES.map((size) => <option key={size} value={size}>{size}</option>)}
            </select>
          </label>
        </div>
      </div>

      <div className={styles.colHeaders}>
        <div>DATE</div>
        <div>MEETING</div>
        <div>AI SUMMARY</div>
        <div>KEYWORDS</div>
      </div>

      <div className={styles.rows} aria-live="polite">
        {error && <p className={styles.message}>{error} Check that the Meeting Insights API is running.</p>}
        {!error && !loading && data?.items.length === 0 && <p className={styles.message}>No meetings found for this date range.</p>}
        {data?.items.map((meeting) => <CallRow key={meeting.meeting_id} meeting={meeting} />)}
      </div>

      <div className={styles.pagination}>
        <span>{total ? `Page ${page} of ${totalPages}` : 'No results'}</span>
        <div>
          <button disabled={page === 1 || loading} onClick={() => { setLoading(true); setError(null); setPage((current) => current - 1); }}>Previous</button>
          <button disabled={page >= totalPages || loading} onClick={() => { setLoading(true); setError(null); setPage((current) => current + 1); }}>Next</button>
        </div>
      </div>
    </section>
  );
}
