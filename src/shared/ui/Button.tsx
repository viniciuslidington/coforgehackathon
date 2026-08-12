'use client';

import type { ReactNode, ButtonHTMLAttributes } from 'react';
import styles from './Button.module.css';

/* ── Variant Types ─────────────────────────────────────────── */

type ButtonVariant = 'primary' | 'secondary' | 'ghost';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  children: ReactNode;
}

export function Button({
  variant = 'secondary',
  children,
  className,
  ...rest
}: ButtonProps) {
  const cls = [styles.btn, styles[variant], className].filter(Boolean).join(' ');
  return (
    <button className={cls} {...rest}>
      {children}
    </button>
  );
}
