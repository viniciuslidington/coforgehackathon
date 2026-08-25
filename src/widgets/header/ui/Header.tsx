'use client';

import { TopicsPicker } from '@/features/call-filters/ui/TopicsPicker';
import styles from './Header.module.css';

interface HeaderProps {
  topics?: string[];
  onTopicsChange?: (topics: string[]) => void;
}

export function Header({ topics = [], onTopicsChange }: HeaderProps) {
  return (
    <header className={styles.header}>
      <div>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>Shift Overview</h1>
        </div>
      </div>
      <div className={styles.actions}>
        {onTopicsChange && (
          <TopicsPicker topics={topics} onChange={onTopicsChange} />
        )}
      </div>
    </header>
  );
}
