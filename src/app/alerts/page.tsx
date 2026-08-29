'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Sidebar } from '@/widgets/sidebar/ui/Sidebar';
import styles from './alerts.module.css';

type Severity = 'all' | 'critical' | 'high' | 'medium';

interface AnomalyAlert {
  id: string;
  title: string;
  severity: 'critical' | 'high' | 'medium';
  meetingTitle: string;
  speakers: string[];
  diagnostic: string;
  tags: string[];
  timeAgo: string;
  timestamp: string;
  status: 'active' | 'resolved';
}

const INITIAL_ALERTS: AnomalyAlert[] = [
  {
    id: 'alt-1',
    title: 'Critical FX Spread Discrepancy (BRL/USD)',
    severity: 'critical',
    meetingTitle: 'Morning FX Desk & Flow Briefing',
    speakers: ['CITI-FX (Marcus S.)', 'Desk Trader B'],
    diagnostic:
      'Spread detected at 12bps above the 30-day moving average. Three participants reported defensiveness and a sharp pullback from liquidity providers ahead of the US inflation release.',
    tags: ['#BRLUSD', '#SpreadDivergence', '#LiquidityRisk'],
    timeAgo: '18 min ago',
    timestamp: '09:30 AM',
    status: 'active',
  },
  {
    id: 'alt-2',
    title: 'Volume Volatility Alert at Sector Open',
    severity: 'critical',
    meetingTitle: 'Equities Pre-Market Sync',
    speakers: ['Head Equities (Andre K.)'],
    diagnostic:
      'Atypical block-order flow in the Energy sector (Oil/O&G) with volume 320% above the standard deviation for the first minute of trading.',
    tags: ['#EnergyFlow', '#BlockOrders', '#Volatility'],
    timeAgo: '34 min ago',
    timestamp: '09:14 AM',
    status: 'active',
  },
  {
    id: 'alt-3',
    title: 'Hesitation and Compliance Risk on Cross Order',
    severity: 'high',
    meetingTitle: 'Treasury & Liquidity Operations Call',
    speakers: ['Desk Chief (Elena V.)', 'Trader Marco'],
    diagnostic:
      'Explicit request identified for a double-check before executing a $40M institutional cross-order above the pre-approved tolerance limit.',
    tags: ['#Compliance', '#CrossOrder', '#TreasuryLimit'],
    timeAgo: '52 min ago',
    timestamp: '08:56 AM',
    status: 'active',
  },
  {
    id: 'alt-4',
    title: 'Missing Quorum on Handoff Alignment',
    severity: 'medium',
    meetingTitle: 'Commodities Desk Sync',
    speakers: ['Commodities Trader 1'],
    diagnostic:
      'Only 1 trader present at the start of the sync call; overnight book handoff logged with a 15-minute operational delay.',
    tags: ['#DeskHandoff', '#Commodities', '#Operations'],
    timeAgo: '1h 10min ago',
    timestamp: '08:38 AM',
    status: 'active',
  },
];

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AnomalyAlert[]>(INITIAL_ALERTS);
  const [selectedSeverity, setSelectedSeverity] = useState<Severity>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [scanning, setScanning] = useState(false);

  const handleResolve = (id: string) => {
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === id
          ? { ...a, status: a.status === 'active' ? 'resolved' : 'active' }
          : a
      )
    );
  };

  const handleRunScan = () => {
    setScanning(true);
    setTimeout(() => {
      setScanning(false);
    }, 1200);
  };

  const filteredAlerts = alerts.filter((item) => {
    if (selectedSeverity !== 'all' && item.severity !== selectedSeverity) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchText =
        item.title.toLowerCase().includes(q) ||
        item.diagnostic.toLowerCase().includes(q) ||
        item.meetingTitle.toLowerCase().includes(q) ||
        item.tags.some((t) => t.toLowerCase().includes(q));
      if (!matchText) return false;
    }
    return true;
  });

  const activeCount = alerts.filter((a) => a.status === 'active').length;
  const criticalCount = alerts.filter((a) => a.severity === 'critical' && a.status === 'active').length;
  const highCount = alerts.filter((a) => a.severity === 'high' && a.status === 'active').length;
  const resolvedCount = alerts.filter((a) => a.status === 'resolved').length;

  return (
    <div className={styles.shell}>
      <Sidebar />

      <main className={styles.main}>
        {/* Top Header */}
        <header className={styles.header}>
          <div className={styles.titleGroup}>
            <div className={styles.titleRow}>
              <h1 className={styles.title}>Anomalies & Alerts</h1>
              <div className={styles.badgeLive}>
                <span className={styles.liveDot} />
                <span>{activeCount} ACTIVE · AI MONITORING</span>
              </div>
            </div>
            <p className={styles.subtitle}>
              Continuous detection of operational deviations, critical spreads, and risk mentions via LangGraph
            </p>
          </div>

          <button
            type="button"
            className={styles.scanBtn}
            onClick={handleRunScan}
            disabled={scanning}
            title="Run an anomaly scan on recent meetings"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
            </svg>
            {scanning ? 'Scanning...' : 'Run Anomaly Scan'}
          </button>
        </header>

        {/* Top KPI Metrics Banner */}
        <div className={styles.kpiGrid}>
          <div className={`${styles.kpiCard} ${criticalCount > 0 ? styles.kpiCritical : ''}`}>
            <span className={styles.kpiLabel}>Critical Alerts</span>
            <div className={styles.kpiValueRow}>
              <span className={styles.kpiValue}>{criticalCount}</span>
              <span className={styles.kpiDelta}>Immediate Action</span>
            </div>
          </div>

          <div className={styles.kpiCard}>
            <span className={styles.kpiLabel}>High Severity</span>
            <div className={styles.kpiValueRow}>
              <span className={styles.kpiValue}>{highCount}</span>
              <span className={styles.kpiDelta}>Trader Attention</span>
            </div>
          </div>

          <div className={styles.kpiCard}>
            <span className={styles.kpiLabel}>Resolved This Shift</span>
            <div className={styles.kpiValueRow}>
              <span className={styles.kpiValue}>{resolvedCount}</span>
              <span className={styles.kpiDelta}>Handled</span>
            </div>
          </div>

          <div className={styles.kpiCard}>
            <span className={styles.kpiLabel}>Model Confidence</span>
            <div className={styles.kpiValueRow}>
              <span className={styles.kpiValue}>98.4%</span>
              <span className={styles.kpiDelta}>Local Vector</span>
            </div>
          </div>
        </div>

        {/* Filter Controls Bar */}
        <div className={styles.filterBar}>
          <div className={styles.severityTabs}>
            <button
              type="button"
              className={`${styles.tabBtn} ${selectedSeverity === 'all' ? styles.tabBtnActive : ''}`}
              onClick={() => setSelectedSeverity('all')}
            >
              All ({alerts.length})
            </button>
            <button
              type="button"
              className={`${styles.tabBtn} ${selectedSeverity === 'critical' ? styles.tabBtnActive : ''}`}
              onClick={() => setSelectedSeverity('critical')}
            >
              Critical ({alerts.filter((a) => a.severity === 'critical').length})
            </button>
            <button
              type="button"
              className={`${styles.tabBtn} ${selectedSeverity === 'high' ? styles.tabBtnActive : ''}`}
              onClick={() => setSelectedSeverity('high')}
            >
              High ({alerts.filter((a) => a.severity === 'high').length})
            </button>
            <button
              type="button"
              className={`${styles.tabBtn} ${selectedSeverity === 'medium' ? styles.tabBtnActive : ''}`}
              onClick={() => setSelectedSeverity('medium')}
            >
              Medium ({alerts.filter((a) => a.severity === 'medium').length})
            </button>
          </div>

          <div className={styles.searchBox}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              className={styles.searchInput}
              placeholder="Search by tag, ticker, text..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        {/* Feed of Anomaly Alert Cards */}
        <div className={styles.feedList}>
          {filteredAlerts.length === 0 ? (
            <p style={{ color: 'var(--text-dim)', padding: '24px 0' }}>
              No anomalies found for the selected filters.
            </p>
          ) : (
            filteredAlerts.map((alert) => {
              const isCritical = alert.severity === 'critical';
              const isHigh = alert.severity === 'high';
              const isResolved = alert.status === 'resolved';

              const severityClass = isCritical
                ? styles.alertCardCritical
                : isHigh
                ? styles.alertCardHigh
                : styles.alertCardMedium;

              return (
                <div
                  key={alert.id}
                  className={`${styles.alertCard} ${severityClass}`}
                  style={{ opacity: isResolved ? 0.6 : 1 }}
                >
                  <div className={styles.cardHeader}>
                    <div className={styles.cardTitleGroup}>
                      <div className={styles.cardTitleRow}>
                        {isCritical && <span className={styles.badgeCritical}>CRITICAL</span>}
                        {isHigh && <span className={styles.badgeHigh}>HIGH</span>}
                        {!isCritical && !isHigh && <span className={styles.badgeMedium}>MEDIUM</span>}
                        <h3 className={styles.cardTitle}>{alert.title}</h3>
                      </div>
                      <div className={styles.cardMeta}>
                        <span>Meeting:</span>
                        <span className={styles.cardMeetingTag}>{alert.meetingTitle}</span>
                        <span>·</span>
                        <span>Participants: {alert.speakers.join(', ')}</span>
                      </div>
                    </div>

                    <div className={styles.cardTime}>
                      {alert.timeAgo} ({alert.timestamp})
                    </div>
                  </div>

                  <div className={styles.cardDiagnostic}>
                    <strong>AI Diagnostic: </strong>
                    {alert.diagnostic}
                  </div>

                  <div className={styles.cardTagsRow}>
                    <div className={styles.tagChips}>
                      {alert.tags.map((tag) => (
                        <span key={tag} className={styles.tagChip}>
                          {tag}
                        </span>
                      ))}
                    </div>

                    <div className={styles.cardActions}>
                      <Link href="/" className={`${styles.actionBtn} ${styles.actionBtnPrimary}`}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />
                        </svg>
                        Investigate with AI
                      </Link>

                      <button
                        type="button"
                        className={styles.actionBtn}
                        onClick={() => handleResolve(alert.id)}
                      >
                        {isResolved ? '↩ Reopen Alert' : '✓ Acknowledge / Resolve'}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </main>
    </div>
  );
}

