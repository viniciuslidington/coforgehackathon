'use client';

import { useState } from 'react';
import { Sidebar } from '@/widgets/sidebar/ui/Sidebar';
import styles from './chat.module.css';

interface SourceCitation {
  id: string;
  meetingTitle: string;
  speaker: string;
  time: string;
  quote: string;
  relevance: number;
}

interface Message {
  id: string;
  role: 'user' | 'ai';
  sender: string;
  text: string;
  bullets?: string[];
  sources?: SourceCitation[];
  timestamp: string;
}

const INITIAL_MESSAGES: Message[] = [
  {
    id: 'm1',
    role: 'user',
    sender: 'User',
    text: 'Was there any critical mention of liquidity or FX spread risk in today’s opening shift meetings?',
    timestamp: '09:42',
  },
  {
    id: 'm2',
    role: 'ai',
    sender: 'ResumeAI Intelligence',
    text: 'Yes. During the desk opening call and the regional FX meeting, 2 points of attention were identified with direct impact on spread and liquidity:',
    bullets: [
      'BRL/USD spread divergence: Citi Desk flagged increased volatility ahead of the NY open, with spreads opening up to 12bps above the weekly average.',
      'EUR/USD spot liquidity risk: Treasury Desk reported a temporary liquidity restriction on blocks above $25M pending the 2pm Fed statement.',
      'AI recommendation: Prioritize TWAP execution and monitor the anomaly alerts channel at the 11am close.',
    ],
    sources: [
      {
        id: 's1',
        meetingTitle: 'Morning FX Desk & Flow Briefing',
        speaker: 'CITI-FX (Marcus S.)',
        time: '00:08:42',
        quote: 'We noticed BRL books opening with a stretched 12bps spread, liquidity providers are defensive ahead of the data.',
        relevance: 96,
      },
      {
        id: 's2',
        meetingTitle: 'Treasury & Liquidity Operations Call',
        speaker: 'Desk Chief (Elena V.)',
        time: '00:19:15',
        quote: 'Large EUR orders above 25M should wait or be sliced via algo, the spot book is thin this morning.',
        relevance: 91,
      },
    ],
    timestamp: '09:43',
  },
];

const SUGGESTIONS = [
  'Summary of today’s macro meetings',
  'Which orders had a compliance block?',
  'Was there any mention of rate decisions (Fed/ECB)?',
  'Which topics came up most often this shift?',
];

let idCounter = 100;
function generateId(prefix: string) {
  idCounter += 1;
  return `${prefix}-${idCounter}`;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
  const [draft, setDraft] = useState('');
  const [openSources, setOpenSources] = useState<Record<string, boolean>>({
    m2: true, // open by default to demonstrate feature
  });
  const [contextScope, setContextScope] = useState('all');

  const toggleSources = (msgId: string) => {
    setOpenSources((prev) => ({
      ...prev,
      [msgId]: !prev[msgId],
    }));
  };

  const handleSend = (textToSend?: string) => {
    const query = (textToSend || draft).trim();
    if (!query) return;

    const userMsg: Message = {
      id: generateId('u'),
      role: 'user',
      sender: 'User',
      text: query,
      timestamp: 'Agora',
    };

    const aiMsg: Message = {
      id: generateId('ai'),
      role: 'ai',
      sender: 'ResumeAI Intelligence',
      text: `Analyzing the meeting database with a focus on "${query}"...`,
      bullets: [
        'Semantic cross-reference run against 14 meetings and 3 hoots from the current shift.',
        'No other direct operational blocker recorded for this scope.',
      ],
      sources: [
        {
          id: generateId('src'),
          meetingTitle: 'Shift Operations Sync',
          speaker: 'Trader Desk A',
          time: '00:12:04',
          quote: `Relevant discussion on execution flow and market parameters related to ${query.slice(0, 30)}...`,
          relevance: 88,
        },
      ],
      timestamp: 'Agora',
    };

    setMessages((prev) => [...prev, userMsg, aiMsg]);
    setOpenSources((prev) => ({ ...prev, [aiMsg.id]: true }));
    if (!textToSend) setDraft('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={styles.shell}>
      <Sidebar />

      <main className={styles.main}>
        {/* Header */}
        <header className={styles.header}>
          <div className={styles.modelBadge}>
            <div className={styles.modelLogo}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2Z" />
                <path d="m9 12 2 2 4-4" />
              </svg>
            </div>
            <div className={styles.modelInfo}>
              <div className={styles.modelTitle}>
                ResumeAI Intelligence
                <span className={styles.modelTag}>v2.4 · LangGraph</span>
              </div>
              <span className={styles.modelSub}>
                RAG over transcripts, audio, and summaries in real time
              </span>
            </div>
          </div>

          <div className={styles.headerActions}>
            <select
              className={styles.contextSelect}
              value={contextScope}
              onChange={(e) => setContextScope(e.target.value)}
              title="Data scope for the chat"
            >
              <option value="all">Full Shift (14 Meetings)</option>
              <option value="hoots">Hoots & Quick Audio Only</option>
              <option value="urgent">High Priority/Urgent Meetings</option>
            </select>

            <button
              type="button"
              className={styles.newChatBtn}
              onClick={() => setMessages([INITIAL_MESSAGES[0], INITIAL_MESSAGES[1]])}
              title="Clear and restart conversation"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 5v14M5 12h14" />
              </svg>
              New conversation
            </button>
          </div>
        </header>

        {/* Conversation Stream */}
        <div className={styles.chatContainer}>
          <div className={styles.messagesList}>
            {messages.map((m) => {
              const isUser = m.role === 'user';
              const hasSources = m.sources && m.sources.length > 0;
              const isSourcesExpanded = openSources[m.id];

              return (
                <div
                  key={m.id}
                  className={`${styles.messageRow} ${isUser ? styles.messageRowUser : ''}`}
                >
                  <div className={`${styles.avatar} ${isUser ? styles.avatarUser : styles.avatarAi}`}>
                    {isUser ? 'U' : 'AI'}
                  </div>

                  <div className={`${styles.messageBody} ${isUser ? styles.messageBodyUser : ''}`}>
                    <div className={styles.messageSender}>
                      <span>{m.sender}</span>
                      <span className={styles.metaRow}>{m.timestamp}</span>
                    </div>

                    <div className={`${styles.messageBubble} ${isUser ? styles.messageBubbleUser : styles.messageBubbleAi}`}>
                      <p>{m.text}</p>

                      {m.bullets && (
                        <ul className={styles.bulletList}>
                          {m.bullets.map((b, idx) => (
                            <li key={idx}>{b}</li>
                          ))}
                        </ul>
                      )}

                      {/* Expandable Sources & Citations Component */}
                      {hasSources && (
                        <div className={styles.sourcesWrapper}>
                          <div
                            className={styles.sourcesHeader}
                            onClick={() => toggleSources(m.id)}
                            role="button"
                            tabIndex={0}
                          >
                            <div className={styles.sourcesTitleGroup}>
                              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
                                <line x1="7" y1="7" x2="7.01" y2="7" />
                              </svg>
                              <span>Cited Sources & Evidence</span>
                              <span className={styles.sourcesCountBadge}>
                                {m.sources!.length} excerpts
                              </span>
                            </div>
                            <span>{isSourcesExpanded ? '▲ Collapse' : '▼ Expand'}</span>
                          </div>

                          {isSourcesExpanded && (
                            <div className={styles.sourcesList}>
                              {m.sources!.map((s) => (
                                <div key={s.id} className={styles.sourceCard}>
                                  <div className={styles.sourceMeta}>
                                    <span className={styles.sourceMeeting}>
                                      {s.meetingTitle}
                                    </span>
                                    <span>·</span>
                                    <span className={styles.sourceSpeaker}>
                                      {s.speaker}
                                    </span>
                                    <span className={styles.sourceTime}>
                                      ⏱ {s.time}
                                    </span>
                                  </div>
                                  <p className={styles.sourceQuote}>
                                    &ldquo;{s.quote}&rdquo;
                                  </p>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Floating Input Dock */}
        <div className={styles.inputDock}>
          <div className={styles.inputInner}>
            {/* Quick Suggestions Bar */}
            <div className={styles.suggestionsBar}>
              {SUGGESTIONS.map((sug, i) => (
                <button
                  key={i}
                  type="button"
                  className={styles.suggestionChip}
                  onClick={() => handleSend(sug)}
                >
                  <span>✦</span>
                  <span>{sug}</span>
                </button>
              ))}
            </div>

            {/* Input Card */}
            <div className={styles.inputCard}>
              <textarea
                className={styles.textarea}
                placeholder="Ask about any meeting, asset mention, decision, or participant from this shift..."
                value={draft}
                rows={1}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={handleKeyDown}
              />
              <button
                type="button"
                className={styles.sendBtn}
                disabled={!draft.trim()}
                onClick={() => handleSend()}
                aria-label="Send message"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            </div>

            <div className={styles.inputFooterNote}>
              ResumeAI can pull direct, timestamped quotes from recorded transcripts.
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
