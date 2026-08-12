'use client';

import { useState, useCallback, useMemo } from 'react';
import type { Call, ChatMessage } from '@/entities/call/model/types';
import { CALLS } from '@/entities/call/model/data';
import { generateAnswer } from '@/entities/call/lib/helpers';

export function useCallDetail() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [rangeA, setRangeA] = useState<number | null>(null);
  const [rangeB, setRangeB] = useState<number | null>(null);
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const selectedCall = useMemo(
    () => CALLS.find(c => c.id === selectedId) ?? null,
    [selectedId],
  );

  const openCall = useCallback((call: Call) => {
    setSelectedId(call.id);
    setRangeA(null);
    setRangeB(null);
    setDraft('');
    setMessages([
      {
        role: 'ai',
        text: 'Summary of the full call is above. Select a range on the left to scope my answers to part of it, or ask anything now.',
      },
    ]);
  }, []);

  const closeCall = useCallback(() => {
    setSelectedId(null);
  }, []);

  const pickSegment = useCallback((index: number) => {
    setRangeA(prev => {
      if (prev === null || rangeB !== null) {
        setRangeB(null);
        return index;
      }
      const lo = Math.min(prev, index);
      const hi = Math.max(prev, index);
      setRangeA(lo);
      setRangeB(hi);
      return lo;
    });
  }, [rangeB]);

  const clearRange = useCallback(() => {
    setRangeA(null);
    setRangeB(null);
  }, []);

  const isInRange = useCallback(
    (index: number) => {
      if (rangeA === null) return false;
      if (rangeB === null) return index === rangeA;
      return index >= rangeA && index <= rangeB;
    },
    [rangeA, rangeB],
  );

  const rangeText = useMemo(() => {
    if (!selectedCall || rangeA === null) return null;
    const segs = selectedCall.segs;
    if (rangeB === null) return segs[rangeA]?.t ?? null;
    return `${segs[rangeA]?.t}–${segs[rangeB]?.t}`;
  }, [selectedCall, rangeA, rangeB]);

  const sendMessage = useCallback(() => {
    const q = draft.trim();
    if (!q || !selectedCall) return;
    setDraft('');
    setMessages(prev => [
      ...prev,
      { role: 'user', text: q },
      { role: 'ai', text: generateAnswer(selectedCall, rangeText) },
    ]);
  }, [draft, selectedCall, rangeText]);

  return {
    selectedCall,
    messages,
    draft,
    setDraft,
    rangeA,
    rangeB,
    rangeText,
    openCall,
    closeCall,
    pickSegment,
    clearRange,
    isInRange,
    sendMessage,
  } as const;
}
