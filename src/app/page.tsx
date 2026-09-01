'use client';

import { useCallback, useMemo } from 'react';
import { filterMeetings, sortMeetings } from '@/entities/meeting/lib/helpers';
import { Sidebar } from '@/widgets/sidebar/ui/Sidebar';
import { Header } from '@/widgets/header/ui/Header';
import { CallHistory } from '@/widgets/call-history/ui/CallHistory';
import { useMeetingHistory } from '@/widgets/call-history/model/useMeetingHistory';
import { QuickChat } from '@/features/quick-chat/ui/QuickChat';
import { useCallFilters } from '@/features/call-filters/model/useCallFilters';
import { useTopics } from '@/features/call-filters/model/useTopics';
import { useMeetingScope } from '@/features/meeting-scope/model/useMeetingScope';
import { useSplitLayout } from '@/features/split-layout/model/useSplitLayout';
import { SplitHandle } from '@/features/split-layout/ui/SplitHandle';
import { useMeetingDetail, type TranscriptSeek } from '@/features/call-detail/model/useMeetingDetail';
import { MeetingDetailModal } from '@/features/call-detail/ui/MeetingDetailModal';
import { getMeetingById } from '@/shared/api/meetings';
import styles from './page.module.css';

export default function ShiftBriefingPage() {
  const { topics, applyTopics } = useTopics();
  const hasTopics = topics.length > 0;

  const filters = useCallFilters(hasTopics);
  const backendSort = filters.sortColumn === 'priority' ? 'priority' : 'time';
  const history = useMeetingHistory(topics, backendSort);

  // The rows actually rendered by the table. Both helpers are pure, so this
  // needs no effect — which is what lets the Quick Chat scope stay in sync
  // with the table without a forbidden state-sync effect.
  const visibleMeetings = useMemo(
    () => sortMeetings(
      filterMeetings(history.items, filters.typeFilter, filters.priorityFilter),
      filters.sortColumn,
      filters.sortDirection,
    ),
    [history.items, filters.typeFilter, filters.priorityFilter, filters.sortColumn, filters.sortDirection],
  );

  const visibleMeetingIds = useMemo(
    () => visibleMeetings.map(meeting => meeting.meeting_id),
    [visibleMeetings],
  );
  const scope = useMeetingScope(visibleMeetingIds);

  // Lifted to the page so a meeting cited in the Quick Chat opens the same
  // modal a table row does.
  const detail = useMeetingDetail();
  // Destructured so the container ref is its own binding: reading other
  // fields off a hook result that also carries a ref reads as ref access.
  const {
    containerRef: splitRef, chatPercent, dragging, maximized,
    reset: resetSplit, handleProps,
  } = useSplitLayout();

  const openMeetingById = useCallback(async (
    meetingId: string,
    seek: TranscriptSeek | null = null,
  ) => {
    const onScreen = visibleMeetings.find(meeting => meeting.meeting_id === meetingId);
    if (onScreen) {
      detail.openMeeting(onScreen, seek);
      return;
    }
    try {
      // A cited meeting may sit outside the current page of the table.
      detail.openMeeting(await getMeetingById(meetingId), seek);
    } catch {
      // Nothing actionable for the user here; leave the modal closed.
    }
  }, [visibleMeetings, detail]);

  // A Quick Chat citation names a meeting and a moment inside it. The seek
  // rides along with the open so it is in place before the transcript lands.
  const openMeetingAt = useCallback((
    meetingId: string,
    from: number | null,
    to: number | null,
  ) => openMeetingById(
    meetingId,
    from === null ? null : { from, to, nonce: Date.now() },
  ), [openMeetingById]);

  return (
    <div className={styles.shell}>
      <Sidebar />

      <main className={styles.main}>
        <Header topics={topics} onTopicsChange={applyTopics} />

        <div className={styles.columns} ref={splitRef}>
          {!maximized && (
            <div className={styles.tablePane}>
              <CallHistory
                history={history}
                filters={filters}
                meetings={visibleMeetings}
                hasTopics={hasTopics}
                onOpenMeeting={detail.openMeeting}
              />
            </div>
          )}

          <SplitHandle
            chatPercent={chatPercent}
            dragging={dragging}
            maximized={maximized}
            onReset={resetSplit}
            handleProps={handleProps}
          />

          <div
            className={styles.chatPane}
            // Percent rather than pixels, so the split survives a resize.
            style={{ flexBasis: maximized ? '100%' : `${chatPercent}%` }}
          >
            <QuickChat
              scope={scope.scope}
              preset={scope.preset}
              onSelectPreset={scope.selectPreset}
              range={scope.range}
              onRangeFromChange={scope.setRangeFrom}
              onRangeToChange={scope.setRangeTo}
              rangeIsComplete={scope.rangeIsComplete}
              onOpenMeeting={openMeetingById}
            onOpenMeetingAt={openMeetingAt}
            />
          </div>
        </div>

        {detail.selectedMeeting && (
          <MeetingDetailModal
            meeting={detail.selectedMeeting}
            segments={detail.segments}
            segmentsLoading={detail.segmentsLoading}
            segmentsError={detail.segmentsError}
            messages={detail.messages}
            draft={detail.draft}
            asking={detail.asking}
            steps={detail.steps}
            onClose={detail.closeMeeting}
            onDraftChange={detail.setDraft}
            onSend={detail.sendMessage}
            seek={detail.seek}
            onSeek={detail.seekTo}
          />
        )}
      </main>
    </div>
  );
}
