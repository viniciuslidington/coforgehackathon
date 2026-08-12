'use client';

import { Sidebar } from '@/widgets/sidebar/ui/Sidebar';
import { Header } from '@/widgets/header/ui/Header';
import { SummaryStrip } from '@/widgets/summary-strip/ui/SummaryStrip';
import { CallHistory } from '@/widgets/call-history/ui/CallHistory';
import { QuickChat } from '@/features/quick-chat/ui/QuickChat';
import { CallDetailModal } from '@/features/call-detail/ui/CallDetailModal';
import { useCallFilters } from '@/features/call-filters/model/useCallFilters';
import { useCallDetail } from '@/features/call-detail/model/useCallDetail';
import { BRIEF } from '@/entities/call/model/data';
import styles from './page.module.css';

export default function ShiftBriefingPage() {
  const { period, sort, selectPeriod, selectSort } = useCallFilters();
  const {
    selectedCall,
    messages,
    draft,
    setDraft,
    rangeText,
    openCall,
    closeCall,
    pickSegment,
    clearRange,
    isInRange,
    sendMessage,
  } = useCallDetail();

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
          <CallHistory
            period={period}
            sort={sort}
            onPeriodChange={selectPeriod}
            onSortChange={selectSort}
            onCallClick={openCall}
          />
          <QuickChat />
        </div>
      </main>

      {selectedCall && (
        <CallDetailModal
          call={selectedCall}
          messages={messages}
          draft={draft}
          rangeText={rangeText}
          isInRange={isInRange}
          onPickSegment={pickSegment}
          onClose={closeCall}
          onDraftChange={setDraft}
          onSend={sendMessage}
          onClearRange={clearRange}
        />
      )}
    </div>
  );
}
