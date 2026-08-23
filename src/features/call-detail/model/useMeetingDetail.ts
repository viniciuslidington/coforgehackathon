'use client';

import { useState, useCallback, useEffect } from 'react';
import type { ChatMessage, MeetingSegment, MeetingSummary } from '@/entities/meeting/model/types';
import { askMeetingQuestion, getMeetingTranscript } from '@/shared/api/meetings';

export function useMeetingDetail() {
  const [selectedMeeting, setSelectedMeeting] = useState<MeetingSummary | null>(null);
  const [segments, setSegments] = useState<MeetingSegment[]>([]);
  const [segmentsLoading, setSegmentsLoading] = useState(false);
  const [segmentsError, setSegmentsError] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [asking, setAsking] = useState(false);

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
    setAsking(false);
    setMessages([
      { role: 'ai', text: 'Ask anything about this meeting.' },
    ]);
  }, []);

  const closeMeeting = useCallback(() => {
    setSelectedMeeting(null);
  }, []);

  const sendMessage = useCallback(() => {
    const q = draft.trim();
    if (!q || !selectedMeeting || asking) return;
    setDraft('');
    setAsking(true);
    setMessages(prev => [
      ...prev,
      { role: 'user', text: q },
      { role: 'ai', text: 'Thinking…' },
    ]);
    askMeetingQuestion(selectedMeeting.meeting_id, q)
      .then((answer) => {
        setMessages(prev => [...prev.slice(0, -1), { role: 'ai', text: answer }]);
      })
      .catch((error: unknown) => {
        const text = error instanceof Error ? error.message : 'Could not get an answer.';
        setMessages(prev => [...prev.slice(0, -1), { role: 'ai', text }]);
      })
      .finally(() => {
        setAsking(false);
      });
  }, [draft, selectedMeeting, asking]);

  return {
    selectedMeeting,
    segments,
    segmentsLoading,
    segmentsError,
    messages,
    draft,
    setDraft,
    asking,
    openMeeting,
    closeMeeting,
    sendMessage,
  } as const;
}
