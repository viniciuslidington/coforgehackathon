'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { Briefing, MeetingScope, ScopeResolution } from '@/entities/meeting/model/scope';
import type { ChatMessage } from '@/entities/meeting/model/types';
import { askQuickChat, generateBriefing, lookupBriefing } from '@/shared/api/quick-chat';

const isAbort = (error: unknown) => error instanceof DOMException && error.name === 'AbortError';
const messageOf = (error: unknown, fallback: string) =>
  error instanceof Error ? error.message : fallback;

export function useQuickChat(scope: MeetingScope | null) {
  const [resolution, setResolution] = useState<ScopeResolution | null>(null);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [briefingSteps, setBriefingSteps] = useState<string[]>([]);
  const [briefingLoading, setBriefingLoading] = useState(true);
  const [briefingError, setBriefingError] = useState<string | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [asking, setAsking] = useState(false);
  const [steps, setSteps] = useState<string[]>([]);

  // Minted on first send rather than during render: crypto.randomUUID() at
  // render time would differ between server and client markup.
  const sessionRef = useRef<string | null>(null);
  const questionController = useRef<AbortController | null>(null);

  const scopeKey = scope ? JSON.stringify(scope) : '';

  useEffect(() => {
    if (!scopeKey) {
      setResolution(null);
      setBriefing(null);
      setBriefingLoading(false);
      return;
    }

    const controller = new AbortController();
    const activeScope = JSON.parse(scopeKey) as MeetingScope;
    let active = true;

    // Every setState below runs in a promise callback, never in the effect
    // body — the project's lint rules forbid the latter.
    setBriefingLoading(true);
    lookupBriefing(activeScope, controller.signal)
      .then(({ scope: resolved, briefing: cached }) => {
        if (!active) return undefined;
        setResolution(resolved);
        setBriefingError(null);
        if (cached) {
          // Cache-first: a briefing already exists for these meetings.
          setBriefing(cached);
          setBriefingLoading(false);
          return undefined;
        }
        setBriefing(null);
        setBriefingSteps([]);
        return generateBriefing(activeScope, event => {
          if (!active) return;
          if (event.type === 'step') {
            setBriefingSteps(current => [...current, event.label]);
          } else if (event.type === 'briefing') {
            setBriefing(event.briefing);
            setBriefingSteps([]);
          } else {
            setBriefingError(event.detail);
            setBriefingSteps([]);
          }
        }, controller.signal).finally(() => {
          if (active) setBriefingLoading(false);
        });
      })
      .catch((error: unknown) => {
        if (!active || isAbort(error)) return;
        setBriefingError(messageOf(error, 'Could not load the briefing.'));
        setBriefingSteps([]);
        setBriefingLoading(false);
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [scopeKey]);

  const sendMessage = useCallback(async () => {
    const question = draft.trim();
    if (!question || !scope || asking) return;

    sessionRef.current ??= crypto.randomUUID();
    const controller = new AbortController();
    questionController.current = controller;

    setDraft('');
    setAsking(true);
    setSteps([]);
    setMessages(previous => [...previous, { role: 'user', text: question }]);

    try {
      await askQuickChat(question, sessionRef.current, scope, event => {
        if (controller.signal.aborted) return;
        if (event.type === 'step') {
          setSteps(current => [...current, event.label]);
        } else if (event.type === 'answer') {
          setMessages(previous => [...previous, {
            role: 'ai',
            text: event.text,
            meetings: event.referenced_meetings,
          }]);
          setSteps([]);
        } else {
          setMessages(previous => [...previous, { role: 'ai', text: event.detail }]);
          setSteps([]);
        }
      }, controller.signal);
    } catch (error: unknown) {
      if (!isAbort(error)) {
        setMessages(previous => [...previous, {
          role: 'ai',
          text: messageOf(error, 'Could not get an answer.'),
        }]);
        setSteps([]);
      }
    } finally {
      if (questionController.current === controller) {
        questionController.current = null;
        setAsking(false);
      }
    }
  }, [draft, scope, asking]);

  return {
    resolution,
    briefing,
    briefingSteps,
    briefingLoading,
    briefingError,
    messages,
    draft,
    setDraft,
    asking,
    steps,
    sendMessage,
  } as const;
}
