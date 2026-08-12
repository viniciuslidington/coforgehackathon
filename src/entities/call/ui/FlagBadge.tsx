'use client';

import type { CallFlag } from '../model/types';
import styles from './FlagBadge.module.css';

interface FlagBadgeProps {
  flag: CallFlag;
}

export function FlagBadge({ flag }: FlagBadgeProps) {
  const cls = flag.urgent ? styles.urgent : styles.teal;

  return (
    <div className={`${styles.badge} ${cls}`}>
      <div className={styles.diamond} />
      {flag.label}
    </div>
  );
}
