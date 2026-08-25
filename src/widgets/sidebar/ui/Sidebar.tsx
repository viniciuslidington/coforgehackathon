'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import styles from './Sidebar.module.css';

interface NavItem {
  id: string;
  label: string;
  href: string;
  badge?: number;
  icon: (active: boolean) => React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  {
    id: 'shift',
    label: 'Shift Overview',
    href: '/',
    icon: (active) => (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? '2.2' : '1.8'} strokeLinecap="round" strokeLinejoin="round">
        <rect width="7" height="9" x="3" y="3" rx="1.5" />
        <rect width="7" height="5" x="14" y="3" rx="1.5" />
        <rect width="7" height="9" x="14" y="12" rx="1.5" />
        <rect width="7" height="5" x="3" y="16" rx="1.5" />
      </svg>
    ),
  },
  {
    id: 'chat',
    label: 'AI Quick Chat',
    href: '/chat',
    icon: (active) => (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? '2.2' : '1.8'} strokeLinecap="round" strokeLinejoin="round">
        <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />
        <path d="M12 8v4" />
        <path d="M12 16h.01" />
      </svg>
    ),
  },
  {
    id: 'alerts',
    label: 'Anomalies & Alerts',
    href: '/alerts',
    badge: 2,
    icon: (active) => (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? '2.2' : '1.8'} strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
        <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
      </svg>
    ),
  },
];

export function Sidebar() {
  const [isExpanded, setIsExpanded] = useState(false);
  const pathname = usePathname();
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

  useEffect(() => {
    const checkApi = async () => {
      try {
        const res = await fetch('http://localhost:8000/health', { method: 'GET', signal: AbortSignal.timeout(2000) });
        setApiOnline(res.ok);
      } catch {
        setApiOnline(false);
      }
    };
    checkApi();
    const interval = setInterval(checkApi, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <aside
      className={`${styles.sidebar} ${isExpanded ? styles.expanded : styles.collapsed}`}
      aria-label="Main navigation"
    >
      {/* Header / Logo section */}
      <div className={styles.header}>
        {isExpanded ? (
          <Link href="/" className={styles.fullLogoWrapper} title="ResumeAI Coforge">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/resume_ai.svg"
              alt="ResumeAI Coforge"
              className={styles.fullLogoImg}
            />
          </Link>
        ) : (
          <Link
            href="/"
            className={styles.logoWrapper}
            title="ResumeAI Coforge"
            onClick={() => {
              // Expand sidebar if clicking logo when collapsed
              setIsExpanded(true);
            }}
          >
            <div className={styles.logo}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/resumeai_icon.svg"
                alt="ResumeAI"
                width={26}
                height={26}
              />
            </div>
          </Link>
        )}

        {/* Toggle Expand / Collapse Button */}
        <button
          type="button"
          className={styles.toggleBtn}
          onClick={() => setIsExpanded((prev) => !prev)}
          title={isExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
          aria-label={isExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`${styles.toggleIcon} ${isExpanded ? styles.toggleIconRotated : ''}`}
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
      </div>

      {/* Main Navigation */}
      <nav className={styles.nav}>
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
          return (
            <Link
              key={item.id}
              href={item.href}
              className={`${styles.navItem} ${isActive ? styles.navItemActive : ''}`}
              aria-label={item.label}
            >
              <span className={styles.iconWrapper}>{item.icon(isActive)}</span>
              {isExpanded && <span className={styles.itemLabel}>{item.label}</span>}
              {item.badge !== undefined && (
                <span className={`${styles.badge} ${isExpanded ? styles.badgeInline : ''}`}>
                  {item.badge}
                </span>
              )}
              {!isExpanded && <span className={styles.tooltip}>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Footer Section: API Status & User Profile */}
      <div className={styles.footer}>
        {/* Status Indicator */}
        <div
          className={`${styles.statusBlock} ${isExpanded ? styles.statusBlockExpanded : ''}`}
          title={apiOnline === true ? 'AI Service Connected' : apiOnline === false ? 'AI Service Offline' : 'AI Service Checking...'}
        >
          <span className={`${styles.statusDot} ${apiOnline ? styles.statusOnline : styles.statusOffline}`} />
          {isExpanded ? (
            <div className={styles.statusDetails}>
              <span className={styles.statusTitle}>AI Service</span>
              <span className={styles.statusSubtitle}>{apiOnline ? 'Online' : 'Offline'}</span>
            </div>
          ) : (
            <span className={styles.tooltip}>{apiOnline ? 'AI Service Online' : 'AI Service Offline'}</span>
          )}
        </div>

        {/* User Profile */}
        <div className={`${styles.userBlock} ${isExpanded ? styles.userBlockExpanded : ''}`}>
          <div className={styles.avatarWrapper}>
            <div className={styles.avatar}>U</div>
            <span className={styles.onlineDot} />
          </div>
          {isExpanded ? (
            <div className={styles.userInfo}>
              <span className={styles.userName}>User</span>
              <span className={styles.userRole}>Desk Trader</span>
            </div>
          ) : (
            <span className={styles.tooltip}>User (Desk Trader)</span>
          )}
        </div>

        {/* Expand / Collapse Footer Button */}
        <button
          type="button"
          className={`${styles.footerToggleBtn} ${isExpanded ? styles.footerToggleExpanded : ''}`}
          onClick={() => setIsExpanded((prev) => !prev)}
          title={isExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
          aria-label={isExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`${styles.toggleIcon} ${isExpanded ? styles.toggleIconRotated : ''}`}
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
          {isExpanded && <span className={styles.footerToggleLabel}>Collapse</span>}
          {!isExpanded && <span className={styles.tooltip}>Expand sidebar</span>}
        </button>
      </div>
    </aside>
  );
}
