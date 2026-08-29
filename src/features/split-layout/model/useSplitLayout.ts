'use client';

import { useCallback, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent, KeyboardEvent as ReactKeyboardEvent } from 'react';

/** Share of the row given to the chat, as a percentage of the row's width. */
export const DEFAULT_CHAT_PERCENT = 30;
const MIN_CHAT_PERCENT = 20;
/** Past this, the chat takes the whole row and the table is hidden entirely. */
export const MAXIMIZE_THRESHOLD = 80;
const KEYBOARD_STEP = 4;

const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

/**
 * Drag-to-resize split between the meetings table and the chat.
 *
 * Sizes are percentages rather than pixels so the split survives a window
 * resize. Dragging past `MAXIMIZE_THRESHOLD` hides the table completely and
 * turns the handle into a control that restores the default layout.
 */
export function useSplitLayout() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [chatPercent, setChatPercent] = useState(DEFAULT_CHAT_PERCENT);
  const [dragging, setDragging] = useState(false);

  const maximized = chatPercent >= MAXIMIZE_THRESHOLD;

  const percentFromPointer = useCallback((clientX: number) => {
    const container = containerRef.current;
    if (!container) return null;
    const rect = container.getBoundingClientRect();
    if (rect.width === 0) return null;
    // Measure from the right edge: the chat is the right-hand pane.
    return clamp(((rect.right - clientX) / rect.width) * 100, MIN_CHAT_PERCENT, 100);
  }, []);

  const onPointerDown = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    // Pointer capture routes every later move to this element, so the drag
    // keeps working when the cursor outruns the handle.
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(true);
  }, []);

  const releaseCapture = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    const element = event.currentTarget;
    if (element.hasPointerCapture?.(event.pointerId)) {
      element.releasePointerCapture(event.pointerId);
    }
  }, []);

  const onPointerMove = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    if (!dragging) return;
    const next = percentFromPointer(event.clientX);
    if (next === null) return;

    if (next >= MAXIMIZE_THRESHOLD) {
      // Snap to full width, so no sliver of unusable table is left behind.
      // The drag has to end here: maximizing swaps this element for the
      // restore button, so the pointerup would land on a removed node and
      // leave `dragging` stuck on.
      releaseCapture(event);
      setDragging(false);
      setChatPercent(100);
      return;
    }
    setChatPercent(next);
  }, [dragging, percentFromPointer, releaseCapture]);

  const endDrag = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    releaseCapture(event);
    setDragging(false);
  }, [releaseCapture]);

  const reset = useCallback(() => {
    // Clear the drag too: reset is reachable from the restore button, which
    // only exists in the maximized state a drag can end in.
    setDragging(false);
    setChatPercent(DEFAULT_CHAT_PERCENT);
  }, []);

  const onKeyDown = useCallback((event: ReactKeyboardEvent<HTMLElement>) => {
    // Left grows the chat, matching the direction the handle would travel.
    const delta = event.key === 'ArrowLeft' ? KEYBOARD_STEP
      : event.key === 'ArrowRight' ? -KEYBOARD_STEP
      : 0;
    if (delta !== 0) {
      event.preventDefault();
      setChatPercent(current => {
        const next = clamp(current + delta, MIN_CHAT_PERCENT, 100);
        return next >= MAXIMIZE_THRESHOLD ? 100 : next;
      });
      return;
    }
    if (event.key === 'Home' || event.key === 'Escape') {
      event.preventDefault();
      reset();
    }
  }, [reset]);

  return {
    containerRef,
    chatPercent,
    dragging,
    maximized,
    reset,
    handleProps: { onPointerDown, onPointerMove, onPointerUp: endDrag, onPointerCancel: endDrag, onKeyDown },
  } as const;
}
