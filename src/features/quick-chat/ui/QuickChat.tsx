'use client';

import { useEffect, useRef } from 'react';
import type { MeetingScope, ScopePreset } from '@/entities/meeting/model/scope';
import { ScopeSelector } from '@/features/meeting-scope/ui/ScopeSelector';
import { AgentTrace } from '@/shared/ui/AgentTrace';
import { ChatMessageBubble } from '@/shared/ui/ChatMessageBubble';
import { useQuickChat } from '../model/useQuickChat';
import { BriefingPanel } from './BriefingPanel';
import { ChatInput } from './ChatInput';
import styles from './QuickChat.module.css';

interface QuickChatProps {
  scope: MeetingScope | null;
  preset: ScopePreset;
  onSelectPreset: (preset: ScopePreset) => void;
  range: { from: string; to: string };
  onRangeFromChange: (value: string) => void;
  onRangeToChange: (value: string) => void;
  rangeIsComplete: boolean;
  onOpenMeeting: (meetingId: string) => void;
}

export function QuickChat({
  scope,
  preset,
  onSelectPreset,
  range,
  onRangeFromChange,
  onRangeToChange,
  rangeIsComplete,
  onOpenMeeting,
}: QuickChatProps) {
  const chat = useQuickChat(scope);
  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: 'smooth' });
  }, [chat.messages, chat.steps]);

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.headerRow}>
          <div className={styles.title}>Quick chat</div>
          <div className={styles.scopeLabel}>SCOPE</div>
        </div>
        <ScopeSelector
          preset={preset}
          onSelectPreset={onSelectPreset}
          range={range}
          onRangeFromChange={onRangeFromChange}
          onRangeToChange={onRangeToChange}
          rangeIsComplete={rangeIsComplete}
          resolution={chat.resolution}
          loading={chat.briefingLoading}
        />
      </div>

      <div className={styles.body} ref={bodyRef}>
        <BriefingPanel
          briefing={chat.briefing}
          steps={chat.briefingSteps}
          loading={chat.briefingLoading}
          error={chat.briefingError}
          onOpenMeeting={onOpenMeeting}
        />

        {chat.messages.length > 0 && (
          <div className={styles.messages}>
            {chat.messages.map((message, index) => (
              <ChatMessageBubble
                key={index}
                message={message}
                onOpenMeeting={onOpenMeeting}
              />
            ))}
          </div>
        )}

        {chat.asking && <AgentTrace steps={chat.steps} />}
      </div>

      <ChatInput
        value={chat.draft}
        onChange={chat.setDraft}
        onSend={chat.sendMessage}
        disabled={chat.asking || !scope}
      />
    </div>
  );
}
