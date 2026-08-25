'use client';

import { useState } from 'react';
import { Popover } from '@/shared/ui/Popover';
import styles from './TopicsPicker.module.css';

interface TopicsPickerProps {
  topics: string[];
  onChange: (topics: string[]) => void;
}

export function TopicsPicker({ topics, onChange }: TopicsPickerProps) {
  const [draft, setDraft] = useState('');

  const addTopic = () => {
    const value = draft.trim();
    if (value && !topics.includes(value)) {
      onChange([...topics, value]);
    }
    setDraft('');
  };

  const removeTopic = (topic: string) => {
    onChange(topics.filter((existing) => existing !== topic));
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      addTopic();
    }
  };

  return (
    <Popover
      trigger={({ open, toggle }) => (
        <button
          type="button"
          className={`${styles.trigger} ${open ? styles.triggerOpen : ''}`}
          onClick={toggle}
          aria-haspopup="dialog"
          aria-expanded={open}
        >
          <span className={styles.triggerLabel}>
            Topics{topics.length > 0 ? ` · ${topics.length}` : ''}
          </span>
          <span className={styles.chevron} aria-hidden="true">▾</span>
        </button>
      )}
    >
      <input
        className={styles.input}
        placeholder="Add topic…"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={handleKeyDown}
        autoFocus
      />
      {topics.length > 0 && (
        <div className={styles.chips}>
          {topics.map((topic) => (
            <span key={topic} className={styles.chip}>
              {topic}
              <button
                type="button"
                className={styles.chipRemove}
                aria-label={`Remove topic ${topic}`}
                onClick={() => removeTopic(topic)}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
    </Popover>
  );
}
