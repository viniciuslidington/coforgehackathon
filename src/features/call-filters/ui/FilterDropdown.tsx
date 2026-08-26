'use client';

import type { CallTypeFilter, PriorityFilter } from '@/entities/meeting/model/types';
import { Popover } from '@/shared/ui/Popover';
import styles from './FilterDropdown.module.css';

interface FilterDropdownProps {
  typeFilter: CallTypeFilter;
  onSelectType: (type: CallTypeFilter) => void;
  priorityFilter: PriorityFilter;
  onSelectPriority: (priority: PriorityFilter) => void;
  showPriorityOptions?: boolean;
  onReset?: () => void;
}

const TYPE_OPTIONS: { key: CallTypeFilter; label: string; tone?: 'hoot' | 'group' }[] = [
  { key: 'all', label: 'All Types' },
  { key: 'hoot', label: 'Hoot Calls', tone: 'hoot' },
  { key: 'group', label: 'Group Calls', tone: 'group' },
];

const PRIORITY_OPTIONS: { key: PriorityFilter; label: string; color?: string }[] = [
  { key: 'all', label: 'All Priorities' },
  { key: 'urgent', label: 'Urgent', color: 'var(--urgent)' },
  { key: 'high', label: 'High', color: 'var(--high)' },
  { key: 'normal', label: 'Routine', color: 'var(--text-dimmest)' },
];

export function FilterDropdown({
  typeFilter,
  onSelectType,
  priorityFilter,
  onSelectPriority,
  showPriorityOptions = true,
  onReset,
}: FilterDropdownProps) {
  const isFiltered = typeFilter !== 'all' || priorityFilter !== 'all';

  let triggerLabel = 'Filters: All';
  if (typeFilter !== 'all' && priorityFilter !== 'all') {
    const tLabel = typeFilter === 'hoot' ? 'Hoot' : 'Group';
    const pLabel = priorityFilter === 'urgent' ? 'Urgent' : priorityFilter === 'high' ? 'High' : 'Routine';
    triggerLabel = `Filter: ${tLabel} · ${pLabel}`;
  } else if (typeFilter !== 'all') {
    triggerLabel = typeFilter === 'hoot' ? 'Filter: Hoot Calls' : 'Filter: Group Calls';
  } else if (priorityFilter !== 'all') {
    const pLabel = priorityFilter === 'urgent' ? 'Urgent' : priorityFilter === 'high' ? 'High' : 'Routine';
    triggerLabel = `Filter: ${pLabel}`;
  }

  return (
    <Popover
      trigger={({ open, toggle }) => (
        <button
          type="button"
          className={`${styles.trigger} ${isFiltered ? styles.triggerActive : ''} ${open ? styles.triggerOpen : ''}`}
          onClick={toggle}
          aria-haspopup="dialog"
          aria-expanded={open}
          title="Filter calls by type and priority"
        >
          <svg
            className={styles.filterIcon}
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
          </svg>
          <span className={styles.triggerLabel}>{triggerLabel}</span>
          {isFiltered && <span className={styles.activeDot} />}
          <span className={styles.chevron} aria-hidden="true">▾</span>
        </button>
      )}
    >
      <div className={styles.menu}>
        <div className={styles.header}>
          <span className={styles.headerTitle}>Filter calls</span>
          {isFiltered && onReset && (
            <button type="button" className={styles.resetBtn} onClick={onReset}>
              Reset
            </button>
          )}
        </div>

        {/* Section: Call Type */}
        <div className={styles.section}>
          <div className={styles.sectionTitle}>CALL TYPE</div>
          <div className={styles.optionsList}>
            {TYPE_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                type="button"
                className={`${styles.option} ${typeFilter === opt.key ? styles.optionActive : ''}`}
                onClick={() => onSelectType(opt.key)}
              >
                <span className={styles.optionLabelRow}>
                  {opt.tone === 'hoot' && <span className={styles.dot} style={{ background: 'var(--brand-orange)' }} />}
                  {opt.tone === 'group' && <span className={styles.dot} style={{ background: 'var(--teal-light)' }} />}
                  <span>{opt.label}</span>
                </span>
                {typeFilter === opt.key && <span className={styles.check}>✓</span>}
              </button>
            ))}
          </div>
        </div>

        {/* Section: Priority */}
        {showPriorityOptions && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>PRIORITY LEVEL</div>
            <div className={styles.optionsList}>
              {PRIORITY_OPTIONS.map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  className={`${styles.option} ${priorityFilter === opt.key ? styles.optionActive : ''}`}
                  onClick={() => onSelectPriority(opt.key)}
                >
                  <span className={styles.optionLabelRow}>
                    {opt.color && <span className={styles.dot} style={{ background: opt.color }} />}
                    <span>{opt.label}</span>
                  </span>
                  {priorityFilter === opt.key && <span className={styles.check}>✓</span>}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </Popover>
  );
}

