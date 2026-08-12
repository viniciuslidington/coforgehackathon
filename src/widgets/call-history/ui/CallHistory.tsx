'use client';

import type { Call, SortKey } from '@/entities/call/model/types';
import { CALLS, PERIODS, SORTS } from '@/entities/call/model/data';
import { filterByPeriod, sortCalls } from '@/entities/call/lib/helpers';
import { CallRow } from '@/entities/call/ui/CallRow';
import { PeriodSelector } from '@/features/call-filters/ui/PeriodSelector';
import { SortSelector } from '@/features/call-filters/ui/SortSelector';
import styles from './CallHistory.module.css';

interface CallHistoryProps {
  period: number;
  sort: SortKey;
  onPeriodChange: (minutes: number) => void;
  onSortChange: (key: SortKey) => void;
  onCallClick: (call: Call) => void;
}

export function CallHistory({
  period,
  sort,
  onPeriodChange,
  onSortChange,
  onCallClick,
}: CallHistoryProps) {
  const filtered = filterByPeriod(CALLS, period);
  const sorted = sortCalls(filtered, sort);
  const needsYou = sorted.filter(c => c.tier !== 'normal').length;

  return (
    <div className={styles.panel}>
      {/* Toolbar */}
      <div className={styles.toolbar}>
        <div className={styles.titleGroup}>
          <div className={styles.title}>Call history</div>
          <div className={styles.count}>
            {sorted.length} calls · {needsYou} need you
          </div>
        </div>
        <div className={styles.controls}>
          <PeriodSelector
            periods={PERIODS}
            active={period}
            onSelect={onPeriodChange}
          />
          <SortSelector
            sorts={SORTS}
            active={sort}
            onSelect={onSortChange}
          />
        </div>
      </div>

      {/* Column Headers */}
      <div className={styles.colHeaders}>
        <div>TIME</div>
        <div>COUNTERPARTY</div>
        <div>AI SUMMARY</div>
        <div className={styles.mentionHeader}>MENTIONS</div>
        <div>PRIORITY</div>
      </div>

      {/* Rows */}
      <div className={styles.rows}>
        {sorted.map(call => (
          <CallRow
            key={call.id}
            call={call}
            onClick={() => onCallClick(call)}
          />
        ))}
      </div>
    </div>
  );
}
