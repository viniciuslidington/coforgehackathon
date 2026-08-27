'use client';

import { useEffect, useState } from 'react';
import type { MeetingPeriod, MeetingSummaryPage } from '@/entities/meeting/model/types';
import { filterMeetings, sortMeetings } from '@/entities/meeting/lib/helpers';
import { getMeetingSummaries, syncMeetings } from '@/shared/api/meetings';
import { CallRow } from '@/entities/meeting/ui/CallRow';
import { useMeetingDetail } from '@/features/call-detail/model/useMeetingDetail';
import { MeetingDetailModal } from '@/features/call-detail/ui/MeetingDetailModal';
import { useCallFilters } from '@/features/call-filters/model/useCallFilters';
import { FilterDropdown } from '@/features/call-filters/ui/FilterDropdown';
import styles from './CallHistory.module.css';

const PERIODS: { label: string; value: MeetingPeriod }[] = [
  { label: 'Today', value: 'day' },
  { label: '7 days', value: 'week' },
  { label: '30 days', value: '30d' },
  { label: 'All', value: 'all' },
];
const PAGE_SIZES = [15, 30, 50, 100];

interface CallHistoryProps {
  topics?: string[];
}

export function CallHistory({ topics = [] }: CallHistoryProps) {
  const hasTopics = topics.length > 0;
  const [period, setPeriod] = useState<MeetingPeriod>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [data, setData] = useState<MeetingSummaryPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const meetingDetail = useMeetingDetail();
  const {
    typeFilter,
    setTypeFilter,
    priorityFilter,
    setPriorityFilter,
    sortColumn,
    sortDirection,
    toggleSort,
    resetFilters,
  } = useCallFilters(hasTopics);

  const [prevTopics, setPrevTopics] = useState(topics);
  if (topics !== prevTopics) {
    setPrevTopics(topics);
    setPage(1);
    setLoading(true);
  }

  const backendSort = sortColumn === 'priority' ? 'priority' : 'time';

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    getMeetingSummaries(period, page, pageSize, topics, backendSort, controller.signal)
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
  }, [page, pageSize, period, topics, backendSort]);

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
      const refreshed = await getMeetingSummaries(period, 1, pageSize, topics, backendSort);
      setData(refreshed);
    } catch (syncError: unknown) {
      setError(syncError instanceof Error ? syncError.message : 'Could not sync meetings.');
    } finally {
      setSyncing(false);
      setLoading(false);
    }
  };

  const items = data?.items ?? [];
  const filteredAndSortedItems = sortMeetings(
    filterMeetings(items, typeFilter, priorityFilter),
    sortColumn,
    sortDirection,
  );

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
          <FilterDropdown
            typeFilter={typeFilter}
            onSelectType={setTypeFilter}
            priorityFilter={priorityFilter}
            onSelectPriority={setPriorityFilter}
            showPriorityOptions={hasTopics}
            onReset={resetFilters}
          />
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

      <div className={`${styles.colHeaders} ${hasTopics ? '' : styles.noPriority}`}>
        <button
          type="button"
          className={`${styles.sortableHeader} ${sortColumn === 'date' ? styles.headerActive : ''}`}
          onClick={() => toggleSort('date')}
          title="Sort by date"
        >
          <span>DATE</span>
          <span className={styles.sortIndicator}>
            {sortColumn === 'date' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
          </span>
        </button>

        <button
          type="button"
          className={`${styles.sortableHeader} ${sortColumn === 'type' ? styles.headerActive : ''}`}
          onClick={() => toggleSort('type')}
          title="Sort by call type"
        >
          <span>TYPE</span>
          <span className={styles.sortIndicator}>
            {sortColumn === 'type' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
          </span>
        </button>

        <div>DURATION</div>
        <div>MEETING</div>
        <div>PARTICIPANTS</div>
        <div>AI SUMMARY</div>
        <div>KEYWORDS</div>

        {hasTopics && (
          <button
            type="button"
            className={`${styles.sortableHeader} ${sortColumn === 'priority' ? styles.headerActive : ''}`}
            onClick={() => toggleSort('priority')}
            title="Sort by priority"
          >
            <span>PRIORITY</span>
            <span className={styles.sortIndicator}>
              {sortColumn === 'priority' ? (sortDirection === 'asc' ? '▲' : '▼') : '↕'}
            </span>
          </button>
        )}
      </div>

      <div className={styles.rows} aria-live="polite">
        {error && <p className={styles.message}>{error} Check that the Meeting Insights API is running.</p>}
        {!error && !loading && (data?.items ?? []).length === 0 && (
          <p className={styles.message}>No meetings found for this date range.</p>
        )}
        {!error && !loading && (data?.items ?? []).length > 0 && filteredAndSortedItems.length === 0 && (
          <p className={styles.message}>No meetings match the active filter criteria.</p>
        )}
        {filteredAndSortedItems.map((meeting) => (
          <CallRow key={meeting.meeting_id} meeting={meeting} onOpen={meetingDetail.openMeeting} showPriority={hasTopics} />
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
          steps={meetingDetail.steps}
          onClose={meetingDetail.closeMeeting}
          onDraftChange={meetingDetail.setDraft}
          onSend={meetingDetail.sendMessage}
        />
      )}
    </section>
  );
}
