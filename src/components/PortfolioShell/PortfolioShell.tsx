import type { MouseEvent, ReactNode } from 'react';
import styles from './PortfolioShell.module.css';

export const CONTENT_ID = 'content';

interface PortfolioShellProps {
  /** Spoken by screen readers when the section changes. Empty until the first change. */
  announcement: string;
  children: ReactNode;
}

function skipToContent(event: MouseEvent<HTMLAnchorElement>) {
  // The hash belongs to section routing, so move focus by hand instead of navigating.
  event.preventDefault();
  const content = document.getElementById(CONTENT_ID);
  content?.focus();
  content?.scrollIntoView({ block: 'start' });
}

/** Viewport layout, masthead, skip link, and the live region for section changes. */
export function PortfolioShell({ announcement, children }: PortfolioShellProps) {
  return (
    <div className={styles.shell}>
      <a className={styles.skip} href={`#${CONTENT_ID}`} onClick={skipToContent}>
        Skip to content
      </a>
      <header className={styles.masthead}>
        <div className={styles.identity}>
          <h1 className={styles.name}>Seoyeon Cho</h1>
          <p className={styles.role}>Software Engineer</p>
        </div>
      </header>
      {children}
      <p className="visually-hidden" role="status" aria-live="polite">
        {announcement}
      </p>
    </div>
  );
}
