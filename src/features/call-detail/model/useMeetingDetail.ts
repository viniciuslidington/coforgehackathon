'use client';

import { useState, useCallback, useEffect } from 'react';
import type { ChatMessage, MeetingSegment, MeetingSummary } from '@/entities/meeting/model/types';
import { getMeetingTranscript } from '@/shared/api/meetings';

export function useMeetingDetail() {
  const [selectedMeeting, setSelectedMeeting] = useState<MeetingSummary | null>(null);
  const [segments, setSegments] = useState<MeetingSegment[]>([]);
  const [segmentsLoading, setSegmentsLoading] = useState(false);
  const [segmentsError, setSegmentsError] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  useEffect(() => {
    if (!selectedMeeting) return;
    const controller = new AbortController();
    let active = true;
    setSegmentsLoading(true);
    setSegmentsError(null);
    getMeetingTranscript(selectedMeeting.meeting_id, controller.signal)
      .then((result) => {
        if (active) setSegments(result);
      })
      .catch((error: unknown) => {
        if (!active || (error instanceof DOMException && error.name === 'AbortError')) return;
        setSegmentsError(error instanceof Error ? error.message : 'Could not load transcript.');
        setSegments([]);
      })
      .finally(() => {
        if (active) setSegmentsLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [selectedMeeting]);

  const openMeeting = useCallback((meeting: MeetingSummary) => {
    setSelectedMeeting(meeting);
    setSegments([]);
    setSegmentsError(null);
    setDraft('');
    setMessages([
      {
        role: 'ai',
        text: 'Ask anything about this meeting. The AI Q&A endpoint is not connected yet — this is a UI preview.',
      },
    ]);
  }, []);

  const closeMeeting = useCallback(() => {
    setSelectedMeeting(null);
  }, []);

  const sendMessage = useCallback(() => {
    const q = draft.trim();
    if (!q || !selectedMeeting) return;
    setDraft('');
    setMessages(prev => [
      ...prev,
      { role: 'user', text: q },
      { role: 'ai', text: 'AI Q&A for this meeting is not wired up yet — this reply is a UI placeholder.' },
    ]);
  }, [draft, selectedMeeting]);

  return {
    selectedMeeting,
    segments,
    segmentsLoading,
    segmentsError,
    messages,
    draft,
    setDraft,
    openMeeting,
    closeMeeting,
    sendMessage,
  } as const;
}
