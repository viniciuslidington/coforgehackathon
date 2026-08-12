'use client';

import { Button } from '@/shared/ui/Button';
import styles from './Header.module.css';

interface HeaderProps {
  onReBrief: () => void;
}

export function Header({ onReBrief }: HeaderProps) {
  return (
    <header className={styles.header}>
      <div>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>Shift Briefing</h1>
          <div className={styles.liveBadge}>
            <div className={styles.liveDot} />
            <span className={styles.liveText}>LIVE · 4 HOOTS</span>
          </div>
        </div>
        <div className={styles.subtitle}>
          Welcome back, Renata — <span className={styles.subtitleHighlight}>47 min away</span>, 14 calls and 3 hoot bursts while you were off desk.
        </div>
      </div>
      <div className={styles.actions}>
        <Button variant="secondary">Mark reviewed</Button>
        <Button variant="primary" onClick={onReBrief}>Re-brief last 2h</Button>
      </div>
    </header>
  );
}
