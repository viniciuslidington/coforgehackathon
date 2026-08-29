'use client';

import type { useSplitLayout } from '../model/useSplitLayout';
import styles from './SplitHandle.module.css';

type SplitLayout = ReturnType<typeof useSplitLayout>;

interface SplitHandleProps {
  chatPercent: number;
  dragging: boolean;
  maximized: boolean;
  onReset: () => void;
  handleProps: SplitLayout['handleProps'];
}

export function SplitHandle({ chatPercent, dragging, maximized, onReset, handleProps }: SplitHandleProps) {
  if (maximized) {
    // The table is hidden, so there is nothing left to drag against — the
    // handle becomes the way back to the default layout.
    return (
      <button
        type="button"
        className={`${styles.handle} ${styles.restore}`}
        onClick={onReset}
        title="Restore layout"
        aria-label="Restore layout"
      >
        <span className={styles.chevron} aria-hidden="true">›</span>
      </button>
    );
  }

  return (
    <div
      className={`${styles.handle} ${dragging ? styles.dragging : ''}`}
      role="separator"
      tabIndex={0}
      aria-orientation="vertical"
      aria-label="Resize chat panel"
      aria-valuenow={Math.round(chatPercent)}
      aria-valuemin={20}
      aria-valuemax={100}
      title="Drag to resize · double-click to reset"
      onDoubleClick={onReset}
      {...handleProps}
    >
      <span className={styles.grip} aria-hidden="true" />
    </div>
  );
}
