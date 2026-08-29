'use client';

import styles from './AgentTrace.module.css';

interface AgentTraceProps {
  steps: string[];
}

/** Live list of what the agent is doing while a question is in flight. */
export function AgentTrace({ steps }: AgentTraceProps) {
  if (steps.length === 0) return null;

  return (
    <div className={styles.trace} aria-live="polite" aria-label="Agent activity">
      {steps.map((step, index) => (
        <div className={styles.traceStep} key={`${index}-${step}`}>
          <span className={styles.traceDot} aria-hidden="true" />
          <span>{step}</span>
        </div>
      ))}
    </div>
  );
}
