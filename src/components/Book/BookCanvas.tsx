import { useEffect, useRef } from 'react';
import type { SectionId } from '../../sections';
import { BookStage } from '../../stage/BookStage';
import { assetUrl, bookMeta, MODEL_PATH } from '../../stage/meta';
import type { TabQuads, ViewId } from '../../stage/types';
import styles from './Book.module.css';

interface BookCanvasProps {
  view: ViewId;
  section: SectionId;
  hovered: SectionId | null;
  pressed: SectionId | null;
  reducedMotion: boolean;
  width: number;
  height: number;
  onQuads(quads: TabQuads): void;
  onReady(): void;
  onFail(): void;
}

/** React wrapper around BookStage. Loaded lazily; default export for React.lazy. */
export default function BookCanvas(props: BookCanvasProps) {
  const { view, section, hovered, pressed, reducedMotion, width, height } = props;
  const hostRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<BookStage | null>(null);
  const latest = useRef(props);

  useEffect(() => {
    latest.current = props;
  });

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    // Each stage gets its own canvas, so a discarded one can never share a GL context.
    const canvas = document.createElement('canvas');
    canvas.setAttribute('aria-hidden', 'true');
    host.appendChild(canvas);
    let cancelled = false;
    let stage: BookStage | null = null;
    const initial = latest.current;

    BookStage.create({
      canvas,
      modelUrl: assetUrl(MODEL_PATH),
      meta: bookMeta,
      view: initial.view,
      section: initial.section,
      reducedMotion: initial.reducedMotion,
      width: initial.width,
      height: initial.height,
      handlers: {
        onQuads: (quads) => latest.current.onQuads(quads),
        onContextLost: () => latest.current.onFail(),
      },
    })
      .then((created) => {
        if (cancelled) {
          created.dispose();
          return;
        }
        stage = created;
        stageRef.current = created;
        // Catch up with anything that changed while the model was loading.
        const now = latest.current;
        created.setView(now.view);
        created.resize(now.width, now.height);
        created.setReducedMotion(now.reducedMotion);
        created.setSection(now.section);
        now.onReady();
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        console.warn('The 3D book could not start, so the still image stays in place.', error);
        latest.current.onFail();
      });

    return () => {
      cancelled = true;
      stage?.dispose();
      stageRef.current = null;
      canvas.remove();
    };
  }, []);

  useEffect(() => stageRef.current?.setView(view), [view]);
  useEffect(() => stageRef.current?.setSection(section), [section]);
  useEffect(() => stageRef.current?.setHover(hovered), [hovered]);
  useEffect(() => stageRef.current?.setPressed(pressed), [pressed]);
  useEffect(() => stageRef.current?.setReducedMotion(reducedMotion), [reducedMotion]);
  useEffect(() => stageRef.current?.resize(width, height), [width, height]);

  // Pointer parallax, for mice and trackpads only.
  useEffect(() => {
    if (reducedMotion || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
    const handleMove = (event: PointerEvent) => {
      stageRef.current?.setPointer(
        (event.clientX / window.innerWidth) * 2 - 1,
        (event.clientY / window.innerHeight) * 2 - 1,
      );
    };
    window.addEventListener('pointermove', handleMove, { passive: true });
    return () => window.removeEventListener('pointermove', handleMove);
  }, [reducedMotion]);

  return <div ref={hostRef} className={styles.canvasHost} />;
}
