'use client';

import type { SortKey, SortOption } from '@/entities/call/model/types';
import styles from './SortSelector.module.css';

interface SortSelectorProps {
  sorts: SortOption[];
  active: SortKey;
  onSelect: (key: SortKey) => void;
}

export function SortSelector({ sorts, active, onSelect }: SortSelectorProps) {
  return (
    <div className={styles.wrapper}>
      <span className={styles.label}>Sort</span>
      {sorts.map(s => (
        <button
          key={s.key}
          className={`${styles.option} ${active === s.key ? styles.active : ''}`}
          onClick={() => onSelect(s.key)}
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}
