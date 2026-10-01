'use client';

import type { Priority, PriorityReason } from '../model/types';
import { tierColor, tierLabel } from '../lib/helpers';
import styles from './PriorityBadge.module.css';

interface PriorityBadgeProps {
  tier: Priority;
  score: number;
  reason?: PriorityReason | null;
}

/** One line saying what earned the score, for the badge's tooltip. */
export function priorityExplanation(score: number, reason: PriorityReason | null | undefined): string {
  const points = `Score ${Math.round(score)}/100`;
  if (!reason) return points;
  switch (reason.kind) {
    case 'mentioned':
      return `${points} · mentions “${reason.topic}” ${reason.mentions === 1 ? 'once' : `${reason.mentions} times`}`;
    case 'discussed':
      return `${points} · discusses “${reason.topic}” without naming it`;
    default:
      return `${points} · summary relates to “${reason.topic}”`;
  }
}

export function PriorityBadge({ tier, score, reason }: PriorityBadgeProps) {
  const color = tierColor(tier);
  const label = tierLabel(tier);
  const isRoutine = tier === 'normal';

  return (
    <div className={styles.wrapper} title={priorityExplanation(score, reason)}>
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
