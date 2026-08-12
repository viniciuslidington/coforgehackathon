'use client';

import type { KeyboardEvent } from 'react';
import styles from './ChatInput.module.css';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  placeholder?: string;
  suggestions?: { label: string; onAsk: () => void }[];
}

export function ChatInput({
  value,
  onChange,
  onSend,
  placeholder = 'Ask what happened…',
  suggestions,
}: ChatInputProps) {
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') onSend();
  };

  return (
    <div className={styles.wrapper}>
      {suggestions && suggestions.length > 0 && (
        <div className={styles.suggestions}>
          {suggestions.map(s => (
            <button
              key={s.label}
              className={styles.suggestion}
              onClick={s.onAsk}
            >
              {s.label}
            </button>
          ))}
        </div>
      )}
      <div className={styles.inputRow}>
        <input
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className={styles.input}
        />
        <button className={styles.sendBtn} onClick={onSend}>
          Ask
        </button>
      </div>
    </div>
  );
}
