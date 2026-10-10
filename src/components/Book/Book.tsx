import { lazy, Suspense, useCallback, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { useElementSize } from '../../hooks/useElementSize';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import type { SectionId } from '../../sections';
import { assetUrl, bookMeta, NARROW_QUERY } from '../../stage/meta';
import { restQuads } from '../../stage/quad';
import type { TabQuads, ViewId } from '../../stage/types';
import { BookmarkNavigation, type BookmarkNavigationHandle } from '../BookmarkNavigation/BookmarkNavigation';
import styles from './Book.module.css';

// three.js and the model load after first paint; the poster holds the frame until then.
const BookCanvas = lazy(() => import('./BookCanvas'));

type LiveState = 'pending' | 'ready' | 'failed';

interface BookProps {
  section: SectionId;
}

/**
 * The book stage: a still poster, the live 3D canvas that replaces it, and the
 * bookmark links mapped onto the tab faces. Everything works with the poster alone.
 */
export function Book({ section }: BookProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const navRef = useRef<BookmarkNavigationHandle>(null);
  const size = useElementSize(stageRef);
  const narrow = useMediaQuery(NARROW_QUERY);
  const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)');
  const [live, setLive] = useState<LiveState>('pending');
  const [hovered, setHovered] = useState<SectionId | null>(null);
  const [pressed, setPressed] = useState<SectionId | null>(null);

  const view: ViewId = narrow ? 'mobile' : 'desktop';
  const viewDef = bookMeta.views[view];
  const resting = useMemo(
    () => (size ? restQuads(viewDef, size.width, size.height) : null),
    [viewDef, size],
  );

  const handleQuads = useCallback((quads: TabQuads) => navRef.current?.applyQuads(quads), []);
  const handleReady = useCallback(() => setLive('ready'), []);
  const handleFail = useCallback(() => setLive('failed'), []);

  // If the 3D view goes away, the labels return to the poster's tab positions.
  useLayoutEffect(() => {
    if (live === 'failed' && resting) navRef.current?.applyQuads(resting);
  }, [live, resting]);

  const frameVars = { '--safe-aspect': viewDef.safeAspect, '--frame-aspect': viewDef.aspect } as CSSProperties;

  return (
    <div ref={stageRef} className={styles.stage} data-live={live} style={frameVars}>
      <picture>
        <source media={NARROW_QUERY} srcSet={assetUrl(bookMeta.views.mobile.poster)} />
        <img
          className={styles.poster}
          src={assetUrl(bookMeta.views.desktop.poster)}
          alt="An open book standing upright. A small study is built into its pages: a desk with a laptop, a chair, a bookshelf, and a window. Three bookmarks rise from its top edge."
          decoding="async"
          fetchPriority="high"
          draggable={false}
        />
      </picture>
      {live !== 'failed' && size && (
        <Suspense fallback={null}>
          <BookCanvas
            view={view}
            section={section}
            hovered={hovered}
            pressed={pressed}
            reducedMotion={reducedMotion}
            width={size.width}
            height={size.height}
            onQuads={handleQuads}
            onReady={handleReady}
            onFail={handleFail}
          />
        </Suspense>
      )}
      <BookmarkNavigation ref={navRef} active={section} restQuads={resting} onHover={setHovered} onPress={setPressed} />
    </div>
  );
}
