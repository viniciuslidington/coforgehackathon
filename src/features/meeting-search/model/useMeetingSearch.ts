'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

/** How long typing must pause before the table is re-queried. */
const SEARCH_DEBOUNCE_MS = 300;

/**
 * The table's search box: what is typed (`value`) and what is searched
 * (`query`), which trails typing by a short pause so each keystroke does not
 * cost a request. Debounced in the change handler rather than an effect, so
 * clearing takes effect immediately.
 */
export function useMeetingSearch() {
  const [value, setValue] = useState('');
  const [query, setQuery] = useState('');
  const timer = useRef<number | null>(null);

  const cancelPending = () => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
  };

  useEffect(() => cancelPending, []);

  const change = useCallback((next: string) => {
    setValue(next);
    cancelPending();
    timer.current = window.setTimeout(() => {
      timer.current = null;
      setQuery(next.trim());
    }, SEARCH_DEBOUNCE_MS);
  }, []);

  const clear = useCallback(() => {
    cancelPending();
    setValue('');
    setQuery('');
  }, []);

  return { value, query, change, clear } as const;
}
