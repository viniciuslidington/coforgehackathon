'use client';

import styles from './Sidebar.module.css';

export function Sidebar() {
  return (
    <nav className={styles.sidebar} aria-label="Main navigation">
      {/* Logo */}
      <div className={styles.logo}>S</div>

      {/* Nav Icons */}
      <div className={styles.nav}>
        <div className={styles.navItem} data-active="true" title="Briefing">
          <div className={styles.iconBriefing} />
        </div>
        <div className={styles.navItem} title="Hoot channels">
          <div className={styles.iconHoot} />
        </div>
        <div className={styles.navItem} title="Counterparties">
          <div className={styles.iconCounterparties} />
        </div>
        <div className={styles.navItem} title="Flags">
          <div className={styles.iconFlags} />
          <div className={styles.flagDot} />
        </div>
      </div>

      {/* User Avatar */}
      <div className={styles.avatar}>RV</div>
    </nav>
  );
}
