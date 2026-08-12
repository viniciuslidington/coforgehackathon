'use client';

import type { PeriodOption } from '@/entities/call/model/types';
import styles from './PeriodSelector.module.css';

interface PeriodSelectorProps {
  periods: PeriodOption[];
  active: number;
  onSelect: (minutes: number) => void;
}

export function PeriodSelector({ periods, active, onSelect }: PeriodSelectorProps) {
  return (
    <div className={styles.wrapper}>
      {periods.map(p => (
        <button
          key={p.label}
          className={`${styles.pill} ${active === p.minutes ? styles.active : ''}`}
          onClick={() => onSelect(p.minutes)}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
