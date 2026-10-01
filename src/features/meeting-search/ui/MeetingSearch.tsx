'use client';

import styles from './MeetingSearch.module.css';

interface MeetingSearchProps {
  value: string;
  onChange: (value: string) => void;
  onClear: () => void;
}

export function MeetingSearch({ value, onChange, onClear }: MeetingSearchProps) {
  return (
    <div className={styles.search} role="search">
      <svg className={styles.icon} viewBox="0 0 16 16" aria-hidden="true">
        <circle cx="7" cy="7" r="4.5" />
        <path d="M10.5 10.5 14 14" />
      </svg>
      <input
        className={styles.input}
        type="search"
        value={value}
        placeholder="Search meetings and what was said…"
        aria-label="Search meetings"
        maxLength={200}
        onChange={event => onChange(event.target.value)}
        onKeyDown={event => {
          if (event.key === 'Escape') onClear();
        }}
      />
      {value && (
        <button type="button" className={styles.clear} onClick={onClear} aria-label="Clear search">
          ×
        </button>
      )}
    </div>
  );
}
