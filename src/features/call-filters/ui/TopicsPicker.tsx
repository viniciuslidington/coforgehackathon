'use client';

import { useState } from 'react';
import { Popover } from '@/shared/ui/Popover';
import styles from './TopicsPicker.module.css';

interface TopicsPickerProps {
  topics: string[];
  onChange: (topics: string[]) => void;
  className?: string;
}

const SUGGESTED_TOPICS = [
  'Fed & Rates',
  'Inflation',
  'Earnings',
  'Tech & AI',
  'FX & Currencies',
  'Energy & Oil',
  'Credit & Bonds',
  'M&A',
];

export function TopicsPicker({ topics, onChange, className }: TopicsPickerProps) {
  const [draft, setDraft] = useState('');

  const addTopic = (valueToAdd?: string) => {
    const raw = valueToAdd !== undefined ? valueToAdd : draft;
    const value = raw.trim();
    if (value && !topics.some((t) => t.toLowerCase() === value.toLowerCase())) {
      onChange([...topics, value]);
    }
    if (valueToAdd === undefined) {
      setDraft('');
    }
  };

  const removeTopic = (topicToRemove: string) => {
    onChange(topics.filter((existing) => existing.toLowerCase() !== topicToRemove.toLowerCase()));
  };

  const clearAllTopics = () => {
    onChange([]);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      addTopic();
    }
  };

  const hasTopics = topics.length > 0;

  return (
    <Popover
      align="right"
      className={className}
      panelClassName={styles.popoverPanel}
      trigger={({ open, toggle }) => (
        <button
          type="button"
          className={`${styles.trigger} ${hasTopics ? styles.triggerActive : ''} ${open ? styles.triggerOpen : ''}`}
          onClick={toggle}
          aria-haspopup="dialog"
          aria-expanded={open}
          title="Filter and prioritize meetings by topic"
        >
          <div className={styles.iconBadge}>
            <svg
              className={styles.topicIcon}
              width="13"
              height="13"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
              <line x1="7" y1="7" x2="7.01" y2="7" />
            </svg>
          </div>

          <span className={styles.triggerLabel}>Topics</span>

          {hasTopics ? (
            <span className={styles.countBadge}>{topics.length}</span>
          ) : (
            <span className={styles.allBadge}>All</span>
          )}

          <span className={styles.chevron} aria-hidden="true">
            ▾
          </span>
        </button>
      )}
    >
      <div className={styles.popoverContent}>
        <div className={styles.header}>
          <div className={styles.headerTitleRow}>
            <svg
              className={styles.headerIcon}
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
              <line x1="7" y1="7" x2="7.01" y2="7" />
            </svg>
            <h3 className={styles.headerTitle}>Focus Topics</h3>
          </div>
          <p className={styles.headerSubtitle}>
            Prioritize meetings matching your target topics
          </p>
        </div>

        <div className={styles.inputRow}>
          <input
            className={styles.input}
            placeholder="Add topic (e.g. Fed, Oil, M&A)..."
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
          />
          <button
            type="button"
            className={styles.addButton}
            onClick={() => addTopic()}
            disabled={!draft.trim()}
          >
            Add
          </button>
        </div>

        {/* Active Topics Section */}
        {hasTopics && (
          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <span className={styles.sectionTitle}>
                Active Filters ({topics.length})
              </span>
              <button
                type="button"
                className={styles.clearBtn}
                onClick={clearAllTopics}
              >
                Clear all
              </button>
            </div>
            <div className={styles.chips}>
              {topics.map((topic) => (
                <span key={topic} className={styles.chip}>
                  <span className={styles.chipDot} />
                  <span className={styles.chipText}>{topic}</span>
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
          </div>
        )}

        {/* Suggestions Section */}
        <div className={styles.section}>
          <div className={styles.sectionTitle}>Quick Suggestions</div>
          <div className={styles.suggestedList}>
            {SUGGESTED_TOPICS.map((suggested) => {
              const isSelected = topics.some(
                (t) => t.toLowerCase() === suggested.toLowerCase()
              );
              return (
                <button
                  key={suggested}
                  type="button"
                  className={`${styles.suggestedChip} ${isSelected ? styles.suggestedSelected : ''}`}
                  onClick={() => {
                    if (isSelected) {
                      removeTopic(suggested);
                    } else {
                      addTopic(suggested);
                    }
                  }}
                >
                  {suggested}
                  <span className={styles.suggestedIcon}>
                    {isSelected ? '✓' : '+'}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div className={styles.footerNote}>
          Matching meetings automatically display relevance priority scores.
        </div>
      </div>
    </Popover>
  );
}
