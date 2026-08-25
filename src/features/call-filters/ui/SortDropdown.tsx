'use client';

import type { SortKey } from '@/entities/meeting/model/types';
import { Popover } from '@/shared/ui/Popover';
import styles from './SortDropdown.module.css';

interface SortDropdownProps {
  sort: SortKey;
  onSelect: (key: SortKey) => void;
}

const OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'time', label: 'Most recent' },
  { key: 'priority', label: 'Priority' },
];

export function SortDropdown({ sort, onSelect }: SortDropdownProps) {
  const activeLabel = OPTIONS.find((option) => option.key === sort)?.label ?? OPTIONS[0].label;

  return (
    <Popover
      trigger={({ open, toggle }) => (
        <button
          type="button"
          className={`${styles.trigger} ${open ? styles.triggerOpen : ''}`}
          onClick={toggle}
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          <span className={styles.triggerLabel}>Sort: {activeLabel}</span>
          <span className={styles.chevron} aria-hidden="true">▾</span>
        </button>
      )}
    >
      <div className={styles.menu} role="listbox">
        {OPTIONS.map((option) => (
          <button
            key={option.key}
            type="button"
            role="option"
            aria-selected={sort === option.key}
            className={`${styles.option} ${sort === option.key ? styles.optionActive : ''}`}
            onClick={() => onSelect(option.key)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </Popover>
  );
}
