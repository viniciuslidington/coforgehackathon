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
    title: 'Discrepância Crítica de Spread Cambial (BRL/USD)',
    severity: 'critical',
    meetingTitle: 'Morning FX Desk & Flow Briefing',
    speakers: ['CITI-FX (Marcus S.)', 'Desk Trader B'],
    diagnostic:
      'Detecção de spread 12bps acima da média histórica móvel (30d). Três participantes reportaram defensividade e recuo expressivo de liquidity providers antes da divulgação de inflação americana.',
    tags: ['#BRLUSD', '#SpreadDivergence', '#LiquidityRisk'],
    timeAgo: 'Há 18 min',
    timestamp: '09:30 AM',
    status: 'active',
  },
  {
    id: 'alt-2',
    title: 'Alerta de Volatilidade de Volume em Abertura de Setor',
    severity: 'critical',
    meetingTitle: 'Equities Pre-Market Sync',
    speakers: ['Head Equities (Andre K.)'],
    diagnostic:
      'Fluxo atípico de ordens em bloco no setor de Energia (Petróleo/O&G) com volume 320% acima do desvio padrão do primeiro minuto de pregão.',
    tags: ['#EnergyFlow', '#BlockOrders', '#Volatility'],
    timeAgo: 'Há 34 min',
    timestamp: '09:14 AM',
    status: 'active',
  },
  {
    id: 'alt-3',
    title: 'Hesitação e Risco de Compliance em Ordem Cruzada',
    severity: 'high',
    meetingTitle: 'Treasury & Liquidity Operations Call',
    speakers: ['Desk Chief (Elena V.)', 'Trader Marco'],
    diagnostic:
      'Identificado pedido explícito de dupla checagem para execução de cross-order institucional de $40M acima do limite de tolerância pré-aprovado.',
    tags: ['#Compliance', '#CrossOrder', '#TreasuryLimit'],
    timeAgo: 'Há 52 min',
    timestamp: '08:56 AM',
    status: 'active',
  },
  {
    id: 'alt-4',
    title: 'Ausência de Quórum em Alinhamento de Handoff',
    severity: 'medium',
    meetingTitle: 'Commodities Desk Sync',
    speakers: ['Commodities Trader 1'],
    diagnostic:
      'Apenas 1 operador presente no início da chamada de sincronização; handoff de posições do book noturno registrado com atraso operacional de 15 minutos.',
    tags: ['#DeskHandoff', '#Commodities', '#Operations'],
    timeAgo: 'Há 1h 10min',
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
                <span>{activeCount} ATIVOS · AI MONITORING</span>
              </div>
            </div>
            <p className={styles.subtitle}>
              Detecção contínua de desvios operacionais, spreads críticos e menções de risco via LangGraph
            </p>
          </div>

          <button
            type="button"
            className={styles.scanBtn}
            onClick={handleRunScan}
            disabled={scanning}
            title="Executar varredura de anomalias nas reuniões recentes"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
            </svg>
            {scanning ? 'Escaneando...' : 'Executar Anomaly Scan'}
          </button>
        </header>

        {/* Top KPI Metrics Banner */}
        <div className={styles.kpiGrid}>
          <div className={`${styles.kpiCard} ${criticalCount > 0 ? styles.kpiCritical : ''}`}>
            <span className={styles.kpiLabel}>Alertas Críticos</span>
            <div className={styles.kpiValueRow}>
              <span className={styles.kpiValue}>{criticalCount}</span>
              <span className={styles.kpiDelta}>Ação Imediata</span>
            </div>
          </div>

          <div className={styles.kpiCard}>
            <span className={styles.kpiLabel}>Severidade Alta</span>
            <div className={styles.kpiValueRow}>
              <span className={styles.kpiValue}>{highCount}</span>
              <span className={styles.kpiDelta}>Atenção Trader</span>
            </div>
          </div>

          <div className={styles.kpiCard}>
            <span className={styles.kpiLabel}>Resolvidos no Turno</span>
            <div className={styles.kpiValueRow}>
              <span className={styles.kpiValue}>{resolvedCount}</span>
              <span className={styles.kpiDelta}>Tratados</span>
            </div>
          </div>

          <div className={styles.kpiCard}>
            <span className={styles.kpiLabel}>Confiança do Modelo</span>
            <div className={styles.kpiValueRow}>
              <span className={styles.kpiValue}>98.4%</span>
              <span className={styles.kpiDelta}>Vetor Local</span>
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
              Todos ({alerts.length})
            </button>
            <button
              type="button"
              className={`${styles.tabBtn} ${selectedSeverity === 'critical' ? styles.tabBtnActive : ''}`}
              onClick={() => setSelectedSeverity('critical')}
            >
              Crítico ({alerts.filter((a) => a.severity === 'critical').length})
            </button>
            <button
              type="button"
              className={`${styles.tabBtn} ${selectedSeverity === 'high' ? styles.tabBtnActive : ''}`}
              onClick={() => setSelectedSeverity('high')}
            >
              Alto ({alerts.filter((a) => a.severity === 'high').length})
            </button>
            <button
              type="button"
              className={`${styles.tabBtn} ${selectedSeverity === 'medium' ? styles.tabBtnActive : ''}`}
              onClick={() => setSelectedSeverity('medium')}
            >
              Médio ({alerts.filter((a) => a.severity === 'medium').length})
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
              placeholder="Buscar por tag, ticker, texto..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        {/* Feed of Anomaly Alert Cards */}
        <div className={styles.feedList}>
          {filteredAlerts.length === 0 ? (
            <p style={{ color: 'var(--text-dim)', padding: '24px 0' }}>
              Nenhuma anomalia encontrada para os filtros selecionados.
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
                        <span>Reunião:</span>
                        <span className={styles.cardMeetingTag}>{alert.meetingTitle}</span>
                        <span>·</span>
                        <span>Participantes: {alert.speakers.join(', ')}</span>
                      </div>
                    </div>

                    <div className={styles.cardTime}>
                      {alert.timeAgo} ({alert.timestamp})
                    </div>
                  </div>

                  <div className={styles.cardDiagnostic}>
                    <strong>Diagnóstico IA: </strong>
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
                      <Link href="/chat" className={`${styles.actionBtn} ${styles.actionBtnPrimary}`}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />
                        </svg>
                        Investigar com IA
                      </Link>

                      <button
                        type="button"
                        className={styles.actionBtn}
                        onClick={() => handleResolve(alert.id)}
                      >
                        {isResolved ? '↩ Reabrir Alerta' : '✓ Marcar Ciente / Resolvido'}
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

