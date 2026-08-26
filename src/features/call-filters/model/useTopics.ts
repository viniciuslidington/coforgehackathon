'use client';

import { useState, useEffect, useCallback } from 'react';

const TOPICS_STORAGE_KEY = 'meeting-topics';

export function useTopics() {
  const [topics, setTopics] = useState<string[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);

  // Restore saved topics from localStorage after initial hydration
  useEffect(() => {
    const restoreTopics = window.setTimeout(() => {
      try {
        const saved = window.localStorage.getItem(TOPICS_STORAGE_KEY);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed)) {
            setTopics(parsed);
          }
        }
      } catch {
        // Storage may be unavailable (e.g. Safari private mode)
      } finally {
        setIsLoaded(true);
      }
    }, 0);
    return () => window.clearTimeout(restoreTopics);
  }, []);

  const applyTopics = useCallback((next: string[]) => {
    setTopics(next);
    try {
      window.localStorage.setItem(TOPICS_STORAGE_KEY, JSON.stringify(next));
    } catch {
      // Storage may be unavailable
    }
  }, []);

  return { topics, applyTopics, isLoaded } as const;
}

