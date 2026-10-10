import type { Icon } from '@phosphor-icons/react';
import { Code } from '@phosphor-icons/react/dist/csr/Code';
import { House } from '@phosphor-icons/react/dist/csr/House';
import { SquaresFour } from '@phosphor-icons/react/dist/csr/SquaresFour';
import { useCallback, useImperativeHandle, useLayoutEffect, useRef, type Ref } from 'react';
import { SECTIONS, sectionHref, type SectionId } from '../../sections';
import { quadSize, quadToMatrix3d } from '../../stage/quad';
import type { TabQuads } from '../../stage/types';
import styles from './BookmarkNavigation.module.css';

export interface BookmarkNavigationHandle {
  /** Move the links onto new tab positions without a React render. Called every 3D frame. */
  applyQuads(quads: TabQuads): void;
}

interface BookmarkNavigationProps {
  active: SectionId;
  /** Tab positions at rest for the current stage size, or null before the stage is measured. */
  restQuads: TabQuads | null;
  onHover(section: SectionId | null): void;
  onPress(section: SectionId | null): void;
  ref?: Ref<BookmarkNavigationHandle>;
}

const ICONS: Record<SectionId, Icon> = {
  about: House,
  projects: SquaresFour,
  skills: Code,
};

/** If the narrowest tab is under this width on screen, every tab shows its label alone. */
const ICON_MIN_WIDTH = 92;

/**
 * The only primary navigation. Each link is real text, laid onto the face of its
 * 3D tab with a perspective transform so it reads as printed on the bookmark.
 */
export function BookmarkNavigation({ active, restQuads, onHover, onPress, ref }: BookmarkNavigationProps) {
  const navRef = useRef<HTMLElement>(null);
  const links = useRef(new Map<SectionId, HTMLAnchorElement>());
  const sizes = useRef(new Map<SectionId, { width: number; height: number }>());

  const place = useCallback((quads: TabQuads, measure: boolean) => {
    if (measure || sizes.current.size === 0) {
      let narrowest = Infinity;
      for (const { id } of SECTIONS) {
        const link = links.current.get(id);
        const quad = quads[id];
        if (!link || !quad) continue;
        const size = quadSize(quad);
        sizes.current.set(id, size);
        narrowest = Math.min(narrowest, size.width);
        link.style.width = `${size.width}px`;
        link.style.height = `${size.height}px`;
        link.style.setProperty('--tab-w', size.width.toFixed(2));
      }
      if (navRef.current) navRef.current.dataset.compact = String(narrowest < ICON_MIN_WIDTH);
    }
    for (const { id } of SECTIONS) {
      const link = links.current.get(id);
      const size = sizes.current.get(id);
      const quad = quads[id];
      if (link && size && quad) link.style.transform = quadToMatrix3d(size.width, size.height, quad);
    }
  }, []);

  useLayoutEffect(() => {
    if (restQuads) place(restQuads, true);
  }, [restQuads, place]);

  useImperativeHandle(ref, () => ({ applyQuads: (quads) => place(quads, false) }), [place]);

  return (
    <nav ref={navRef} className={styles.nav} aria-label="Sections" data-ready={restQuads !== null}>
      <ul className={styles.list}>
        {SECTIONS.map(({ id, label }) => {
          const TabIcon = ICONS[id];
          const current = id === active;
          return (
            <li key={id}>
              <a
                ref={(element) => {
                  if (element) links.current.set(id, element);
                  else links.current.delete(id);
                }}
                className={styles.tab}
                href={sectionHref(id)}
                aria-current={current ? 'page' : undefined}
                onPointerEnter={() => onHover(id)}
                onPointerLeave={() => {
                  onHover(null);
                  onPress(null);
                }}
                onPointerDown={() => onPress(id)}
                onPointerUp={() => onPress(null)}
                onPointerCancel={() => onPress(null)}
                onFocus={() => onHover(id)}
                onBlur={() => onHover(null)}
              >
                <TabIcon className={styles.icon} weight={current ? 'fill' : 'regular'} aria-hidden="true" />
                <span className={styles.label}>{label}</span>
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
