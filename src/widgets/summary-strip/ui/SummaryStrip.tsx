import styles from './SummaryStrip.module.css';

interface SummaryCard {
  label: string;
  labelColor: string;
  text: string;
  highlight?: string;
}

const CARDS: SummaryCard[] = [
  {
    label: 'DID I MISS ANYTHING URGENT?',
    labelColor: 'var(--urgent)',
    text: '',
    highlight: '2 anomalies.',
  },
  {
    label: 'WHO TRIED TO REACH ME?',
    labelColor: 'var(--urgent)',
    text: ' called twice, unanswered. Named you 5× on the EUR hoot.',
    highlight: 'CITI-FX',
  },
  {
    label: 'WHAT CHANGED?',
    labelColor: 'var(--text-dim)',
    text: 'Desk tone flipped to risk-off after 14:10 CPI whisper; three counterparties widened 2s10s quotes.',
  },
];

export function SummaryStrip() {
  return (
    <div className={styles.strip}>
      {CARDS.map(card => (
        <div key={card.label} className={styles.card}>
          <div className={styles.label} style={{ color: card.labelColor }}>
            {card.label}
          </div>
          <div className={styles.text}>
            {card.label === 'DID I MISS ANYTHING URGENT?' ? (
              <>
                <span className={styles.bold}>2 anomalies.</span>{' '}
                Off-market bid on 10y JGB via Nomura hoot, 13:58 — 4bp through screen.
              </>
            ) : card.label === 'WHO TRIED TO REACH ME?' ? (
              <>
                <span className={styles.mono}>CITI-FX</span> called twice, unanswered. Named you 5× on the EUR hoot.
              </>
            ) : (
              card.text
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
