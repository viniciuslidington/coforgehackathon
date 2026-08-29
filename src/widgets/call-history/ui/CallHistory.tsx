'use client';

import { useSyncExternalStore } from 'react';
import type { MeetingPeriod, MeetingSummary, SortColumn, SortDirection } from '@/entities/meeting/model/types';
import { CallRow } from '@/entities/meeting/ui/CallRow';
import { FilterDropdown } from '@/features/call-filters/ui/FilterDropdown';
import type { useCallFilters } from '@/features/call-filters/model/useCallFilters';
import type { useMeetingHistory } from '../model/useMeetingHistory';
import styles from './CallHistory.module.css';

const PERIODS: { label: string; value: MeetingPeriod }[] = [
  { label: 'Today', value: 'day' },
  { label: '7 days', value: 'week' },
  { label: '30 days', value: '30d' },
  { label: 'All', value: 'all' },
];
const PAGE_SIZES = [15, 30, 50, 100];

const noopSubscribe = () => () => {};
// `false` during SSR and the first client render, `true` once hydrated.
const useHydrated = () =>
  useSyncExternalStore(noopSubscribe, () => true, () => false);

interface CallHistoryProps {
  history: ReturnType<typeof useMeetingHistory>;
  filters: ReturnType<typeof useCallFilters>;
  /** Already filtered and sorted by the page — the rows actually on screen. */
  meetings: MeetingSummary[];
  hasTopics: boolean;
  onOpenMeeting: (meeting: MeetingSummary) => void;
}

export function CallHistory({ history, filters, meetings, hasTopics, onOpenMeeting }: CallHistoryProps) {
  // The pagination controls below derive their disabled state from
  // client-only data (the fetched page count) and effect-driven flags. Gate
  // that behind a hydration flag so the server render and the first client
  // render always agree, avoiding a hydration mismatch on `disabled`.
  const hydrated = useHydrated();

  const sortIndicator = (column: SortColumn, direction: SortDirection) =>
    filters.sortColumn === column ? (direction === 'asc' ? '▲' : '▼') : '↕';

  return (
    <section className={styles.panel} aria-label="Meeting summaries">
      <div className={styles.toolbar}>
        <div className={styles.titleGroup}>
          <div className={styles.title}>Meeting summaries</div>
          <div className={styles.count}>
            {history.loading ? 'Loading…' : `${history.total} meetings`}
          </div>
        </div>
        <div className={styles.controls}>
          <button className={styles.syncButton} onClick={history.sync} disabled={history.syncing}>
            {history.syncing ? 'Syncing…' : 'Get more meetings'}
          </button>
          <FilterDropdown
            typeFilter={filters.typeFilter}
            onSelectType={filters.setTypeFilter}
            priorityFilter={filters.priorityFilter}
            onSelectPriority={filters.setPriorityFilter}
            showPriorityOptions={hasTopics}
            onReset={filters.resetFilters}
          />
          <div className={styles.periods} aria-label="Date range">
            {PERIODS.map(({ label, value }) => (
              <button
                key={value}
                className={`${styles.period} ${history.period === value ? styles.active : ''}`}
                onClick={() => history.selectPeriod(value)}
              >
                {label}
              </button>
            ))}
          </div>
          <label className={styles.pageSize}>
            Per page
            <select
              value={history.pageSize}
              onChange={event => history.selectPageSize(Number(event.target.value))}
            >
              {PAGE_SIZES.map(size => <option key={size} value={size}>{size}</option>)}
            </select>
          </label>
        </div>
      </div>

      <div className={`${styles.colHeaders} ${hasTopics ? '' : styles.noPriority}`}>
        <button
          type="button"
          className={`${styles.sortableHeader} ${filters.sortColumn === 'date' ? styles.headerActive : ''}`}
          onClick={() => filters.toggleSort('date')}
          title="Sort by date"
        >
          <span>DATE</span>
          <span className={styles.sortIndicator}>{sortIndicator('date', filters.sortDirection)}</span>
        </button>

        <button
          type="button"
          className={`${styles.sortableHeader} ${filters.sortColumn === 'type' ? styles.headerActive : ''}`}
          onClick={() => filters.toggleSort('type')}
          title="Sort by call type"
        >
          <span>TYPE</span>
          <span className={styles.sortIndicator}>{sortIndicator('type', filters.sortDirection)}</span>
        </button>

        <div>DURATION</div>
        <div>MEETING</div>
        <div>PARTICIPANTS</div>
        <div>AI SUMMARY</div>
        <div>KEYWORDS</div>

        {hasTopics && (
          <button
            type="button"
            className={`${styles.sortableHeader} ${filters.sortColumn === 'priority' ? styles.headerActive : ''}`}
            onClick={() => filters.toggleSort('priority')}
            title="Sort by priority"
          >
            <span>PRIORITY</span>
            <span className={styles.sortIndicator}>{sortIndicator('priority', filters.sortDirection)}</span>
          </button>
        )}
      </div>

      <div className={styles.rows} aria-live="polite">
        {history.error && (
          <p className={styles.message}>
            {history.error} Check that the Meeting Insights API is running.
          </p>
        )}
        {!history.error && !history.loading && history.items.length === 0 && (
          <p className={styles.message}>No meetings found for this date range.</p>
        )}
        {!history.error && !history.loading && history.items.length > 0 && meetings.length === 0 && (
          <p className={styles.message}>No meetings match the active filter criteria.</p>
        )}
        {meetings.map(meeting => (
          <CallRow
            key={meeting.meeting_id}
            meeting={meeting}
            onOpen={onOpenMeeting}
            showPriority={hasTopics}
          />
        ))}
      </div>

      <div className={styles.pagination}>
        <span>
          {history.total ? `Page ${history.page} of ${history.totalPages}` : 'No results'}
        </span>
        <div>
          <button
            disabled={!hydrated || history.page === 1 || history.loading}
            onClick={() => history.goToPage(current => current - 1)}
          >
            Previous
          </button>
          <button
            disabled={!hydrated || history.page >= history.totalPages || history.loading}
            onClick={() => history.goToPage(current => current + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </section>
  );
}
