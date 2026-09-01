'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import type { ChatMessage, MeetingSegment, MeetingSummary } from '@/entities/meeting/model/types';

/** A moment in the open meeting's transcript to scroll to and highlight. */
export interface TranscriptSeek {
  from: number;
  to: number | null;
  /** Bumped per request so following the same citation twice re-scrolls. */
  nonce: number;
}
import { askMeetingQuestion, getMeetingTranscript } from '@/shared/api/meetings';

export function useMeetingDetail() {
  const [selectedMeeting, setSelectedMeeting] = useState<MeetingSummary | null>(null);
  const [segments, setSegments] = useState<MeetingSegment[]>([]);
  const [segmentsLoading, setSegmentsLoading] = useState(false);
  const [segmentsError, setSegmentsError] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [asking, setAsking] = useState(false);
  const [steps, setSteps] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  // Owned here rather than in the modal so that opening another meeting clears
  // it along with the rest of the per-meeting state. Left in the modal, a
  // previous meeting's seek would highlight an unrelated cue in the next one.
  const [seek, setSeek] = useState<TranscriptSeek | null>(null);
  const questionController = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!selectedMeeting) return;
    const controller = new AbortController();
    let active = true;
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

  const openMeeting = useCallback((meeting: MeetingSummary, initialSeek?: TranscriptSeek | null) => {
    questionController.current?.abort();
    setSelectedMeeting(meeting);
    setSeek(initialSeek ?? null);
    setSegments([]);
    setSegmentsLoading(true);
    setSegmentsError(null);
    setDraft('');
    setAsking(false);
    setSteps([]);
    setSessionId(crypto.randomUUID());
    setMessages([
      { role: 'ai', text: 'Ask anything about this meeting.' },
    ]);
  }, []);

  const closeMeeting = useCallback(() => {
    questionController.current?.abort();
    questionController.current = null;
    setSelectedMeeting(null);
    setSegments([]);
    setSeek(null);
    setMessages([]);
    setSteps([]);
    setSessionId(null);
    setAsking(false);
  }, []);

  const seekTo = useCallback((from: number, to: number | null) => {
    setSeek(previous => ({ from, to, nonce: (previous?.nonce ?? 0) + 1 }));
  }, []);

  const sendMessage = useCallback(async () => {
    const q = draft.trim();
    if (!q || !selectedMeeting || !sessionId || asking) return;
    const controller = new AbortController();
    questionController.current = controller;
    setDraft('');
    setAsking(true);
    setSteps([]);
    setMessages(prev => [
      ...prev,
      { role: 'user', text: q },
    ]);

    try {
      await askMeetingQuestion(
        selectedMeeting.meeting_id,
        q,
        sessionId,
        (event) => {
          if (controller.signal.aborted) return;
          if (event.type === 'step') {
            setSteps(prev => [...prev, event.label]);
          } else if (event.type === 'answer') {
            setMessages(prev => [...prev, { role: 'ai', text: event.text }]);
            setSteps([]);
          } else {
            setMessages(prev => [...prev, { role: 'ai', text: event.detail }]);
            setSteps([]);
          }
        },
        controller.signal,
      );
    } catch (error: unknown) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) {
        const text = error instanceof Error ? error.message : 'Could not get an answer.';
        setMessages(prev => [...prev, { role: 'ai', text }]);
        setSteps([]);
      }
    } finally {
      if (questionController.current === controller) {
        questionController.current = null;
        setAsking(false);
      }
    }
  }, [draft, selectedMeeting, sessionId, asking]);

  return {
    selectedMeeting,
    segments,
    segmentsLoading,
    segmentsError,
    messages,
    draft,
    setDraft,
    asking,
    steps,
    seek,
    openMeeting,
    closeMeeting,
    sendMessage,
    seekTo,
  } as const;
}
