'use client';

import { useEffect, useState } from 'react';
import type { MeetingPeriod, MeetingSummaryPage } from '@/entities/meeting/model/types';
import { getMeetingSummaries, syncMeetings } from '@/shared/api/meetings';
import { CallRow } from '@/entities/meeting/ui/CallRow';
import { useMeetingDetail } from '@/features/call-detail/model/useMeetingDetail';
import { MeetingDetailModal } from '@/features/call-detail/ui/MeetingDetailModal';
import { useCallFilters } from '@/features/call-filters/model/useCallFilters';
import { SortDropdown } from '@/features/call-filters/ui/SortDropdown';
import { TopicsPicker } from '@/features/call-filters/ui/TopicsPicker';
import styles from './CallHistory.module.css';

const TOPICS_STORAGE_KEY = 'meeting-topics';

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
  const [syncing, setSyncing] = useState(false);
  const meetingDetail = useMeetingDetail();
  const [topics, setTopics] = useState<string[]>([]);
  const { sort, selectSort } = useCallFilters();

  // Deliberately not a lazy useState initializer: this component renders on
  // the server first (no `window`), so restoring from localStorage has to
  // happen post-mount to avoid a hydration mismatch between the server's
  // empty render and the client's real stored value.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(TOPICS_STORAGE_KEY);
      if (saved) setTopics(JSON.parse(saved) as string[]);
    } catch {
      // Storage may be unavailable (e.g. Safari private mode), or hold a
      // stale/invalid value — either way, just keep the empty default.
    }
  }, []);

  const applyTopics = (next: string[]) => {
    setLoading(true);
    setPage(1);
    setTopics(next);
    try {
      window.localStorage.setItem(TOPICS_STORAGE_KEY, JSON.stringify(next));
    } catch {
      // Storage may be unavailable (e.g. Safari private mode) — just skip persisting.
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    getMeetingSummaries(period, page, pageSize, topics, sort, controller.signal)
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
  }, [page, pageSize, period, topics, sort]);

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

  const handleSync = async () => {
    if (loading || syncing) return;
    setSyncing(true);
    setError(null);
    try {
      await syncMeetings();
      setLoading(true);
      setPage(1);
      // Changing the page alone does not retrigger the request when already
      // on page one, so reload the current result explicitly after syncing.
      const refreshed = await getMeetingSummaries(period, 1, pageSize, topics, sort);
      setData(refreshed);
    } catch (syncError: unknown) {
      setError(syncError instanceof Error ? syncError.message : 'Could not sync meetings.');
    } finally {
      setSyncing(false);
      setLoading(false);
    }
  };

  return (
    <section className={styles.panel} aria-label="Meeting summaries">
      <div className={styles.toolbar}>
        <div className={styles.titleGroup}>
          <div className={styles.title}>Meeting summaries</div>
          <div className={styles.count}>{loading ? 'Loading…' : `${total} meetings`}</div>
        </div>
        <div className={styles.controls}>
          <button className={styles.syncButton} onClick={handleSync} disabled={syncing}>
            {syncing ? 'Syncing…' : 'Get more meetings'}
          </button>
          <TopicsPicker topics={topics} onChange={applyTopics} />
          <SortDropdown sort={sort} onSelect={selectSort} />
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
        <div>DURATION</div>
        <div>MEETING</div>
        <div>PARTICIPANTS</div>
        <div>AI SUMMARY</div>
        <div>KEYWORDS</div>
        <div>PRIORITY</div>
      </div>

      <div className={styles.rows} aria-live="polite">
        {error && <p className={styles.message}>{error} Check that the Meeting Insights API is running.</p>}
        {!error && !loading && data?.items.length === 0 && <p className={styles.message}>No meetings found for this date range.</p>}
        {(data?.items ?? []).map((meeting) => (
          <CallRow key={meeting.meeting_id} meeting={meeting} onOpen={meetingDetail.openMeeting} />
        ))}
      </div>

      <div className={styles.pagination}>
        <span>{total ? `Page ${page} of ${totalPages}` : 'No results'}</span>
        <div>
          <button disabled={page === 1 || loading} onClick={() => { setLoading(true); setError(null); setPage((current) => current - 1); }}>Previous</button>
          <button disabled={page >= totalPages || loading} onClick={() => { setLoading(true); setError(null); setPage((current) => current + 1); }}>Next</button>
        </div>
      </div>

      {meetingDetail.selectedMeeting && (
        <MeetingDetailModal
          meeting={meetingDetail.selectedMeeting}
          segments={meetingDetail.segments}
          segmentsLoading={meetingDetail.segmentsLoading}
          segmentsError={meetingDetail.segmentsError}
          messages={meetingDetail.messages}
          draft={meetingDetail.draft}
          asking={meetingDetail.asking}
          onClose={meetingDetail.closeMeeting}
          onDraftChange={meetingDetail.setDraft}
          onSend={meetingDetail.sendMessage}
        />
      )}
    </section>
  );
}
