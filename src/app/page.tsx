'use client';

import { Sidebar } from '@/widgets/sidebar/ui/Sidebar';
import { Header } from '@/widgets/header/ui/Header';
import { CallHistory } from '@/widgets/call-history/ui/CallHistory';
import { QuickChat } from '@/features/quick-chat/ui/QuickChat';
import { useTopics } from '@/features/call-filters/model/useTopics';
import styles from './page.module.css';

export default function ShiftBriefingPage() {
  const { topics, applyTopics } = useTopics();

  return (
    <div className={styles.shell}>
      <Sidebar />

      <main className={styles.main}>
        <Header topics={topics} onTopicsChange={applyTopics} />

        <div className={styles.columns}>
          <CallHistory topics={topics} />
          <QuickChat />
        </div>
      </main>
    </div>
  );
}
