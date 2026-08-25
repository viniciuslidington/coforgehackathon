'use client';

import type { Priority } from '../model/types';
import { tierColor, tierLabel } from '../lib/helpers';
import styles from './PriorityBadge.module.css';

interface PriorityBadgeProps {
  tier: Priority;
  score: number;
}

export function PriorityBadge({ tier, score }: PriorityBadgeProps) {
  const color = tierColor(tier);
  const label = tierLabel(tier);
  const isRoutine = tier === 'normal';

  return (
    <div className={styles.wrapper}>
      <div className={styles.labelRow}>
        <div className={styles.dot} style={{ background: color }} />
        <span
          className={styles.label}
          style={{ color: isRoutine ? 'var(--text-dim)' : color, fontWeight: 500 }}
        >
          {label}
        </span>
      </div>
      <div className={styles.track}>
        <div className={styles.fill} style={{ width: `${score}%`, background: color }} />
      </div>
    </div>
  );
}
