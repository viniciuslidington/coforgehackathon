'use client';

import { Sidebar } from '@/widgets/sidebar/ui/Sidebar';
import { Header } from '@/widgets/header/ui/Header';
import { SummaryStrip } from '@/widgets/summary-strip/ui/SummaryStrip';
import { CallHistory } from '@/widgets/call-history/ui/CallHistory';
import { QuickChat } from '@/features/quick-chat/ui/QuickChat';
import styles from './page.module.css';

export default function ShiftBriefingPage() {
  return (
    <div className={styles.shell}>
      <Sidebar />

      <main className={styles.main}>
        <Header
          onReBrief={() => {
            /* Triggers re-brief for last 2h — wired into chat context */
          }}
        />

        <SummaryStrip />

        <div className={styles.columns}>
          <CallHistory />
          <QuickChat />
        </div>
      </main>
    </div>
  );
}
