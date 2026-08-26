'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import styles from './Popover.module.css';

interface PopoverProps {
  trigger: (props: { open: boolean; toggle: () => void }) => ReactNode;
  children: ReactNode;
  align?: 'left' | 'right';
  className?: string;
  panelClassName?: string;
}

export function Popover({
  trigger,
  children,
  align = 'left',
  className,
  panelClassName,
}: PopoverProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const toggle = () => setOpen((current) => !current);

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  const rootClass = [styles.root, className].filter(Boolean).join(' ');
  const panelClass = [
    styles.panel,
    align === 'right' ? styles.panelRight : styles.panelLeft,
    panelClassName,
  ].filter(Boolean).join(' ');

  return (
    <div className={rootClass} ref={rootRef}>
      {trigger({ open, toggle })}
      {open && <div className={panelClass}>{children}</div>}
    </div>
  );
}
