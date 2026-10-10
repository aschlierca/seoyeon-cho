import type { ReactNode } from 'react';
import { SECTION_BY_ID, type SectionId } from '../../sections';
import styles from './BookPage.module.css';

interface BookPageProps {
  section: SectionId;
  /** Page content. Leave empty and the page says it is blank. */
  children?: ReactNode;
}

/** Shared page layout: marker in the section's hue, title, then content or the blank state. */
export function BookPage({ section, children }: BookPageProps) {
  const { label, hue } = SECTION_BY_ID[section];
  const titleId = `${section}-title`;

  return (
    <section className={styles.page} data-hue={hue} aria-labelledby={titleId}>
      <div className={styles.sheet}>
        <h2 id={titleId} className={styles.title}>
          {label}
        </h2>
        {children ?? <p className={styles.blank}>This page is intentionally left blank.</p>}
      </div>
    </section>
  );
}
