'use client';

import { useEffect, useState } from 'react';
import { getTopicSuggestions, type TopicSuggestion } from '@/shared/api/meetings';

/**
 * Shown until the API answers, and kept if it cannot: a fixed list of
 * common desk topics, so the picker never opens empty.
 */
const FALLBACK_SUGGESTIONS: TopicSuggestion[] = [
  'Fed & Rates',
  'Inflation',
  'Earnings',
  'Tech & AI',
  'FX & Currencies',
  'Energy & Oil',
  'Credit & Bonds',
  'M&A',
].map(topic => ({ topic, meetings: 0 }));

/**
 * Topic suggestions drawn from the keywords of recent meetings, so the
 * picker offers what the desk is actually talking about.
 */
export function useTopicSuggestions() {
  const [suggestions, setSuggestions] = useState<TopicSuggestion[]>(FALLBACK_SUGGESTIONS);
  const [fromMeetings, setFromMeetings] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getTopicSuggestions(controller.signal)
      .then(result => {
        if (result.length === 0) return;
        setSuggestions(result);
        setFromMeetings(true);
      })
      .catch(() => {
        // Keep the fallback list; suggestions are a convenience.
      });
    return () => controller.abort();
  }, []);

  return { suggestions, fromMeetings } as const;
}
