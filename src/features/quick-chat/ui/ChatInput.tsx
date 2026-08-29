'use client';

import type { KeyboardEvent } from 'react';
import styles from './ChatInput.module.css';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  placeholder?: string;
  disabled?: boolean;
}

export function ChatInput({
  value,
  onChange,
  onSend,
  placeholder = 'Ask what happened…',
  disabled = false,
}: ChatInputProps) {
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !disabled) onSend();
  };

  return (
    <div className={styles.wrapper}>
      <div className={styles.inputRow}>
        <input
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className={styles.input}
          disabled={disabled}
        />
        <button className={styles.sendBtn} onClick={onSend} disabled={disabled || !value.trim()}>
          Ask
        </button>
      </div>
    </div>
  );
}
