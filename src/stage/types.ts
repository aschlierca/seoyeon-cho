import type { SectionId } from '../sections';

export type ViewId = 'desktop' | 'mobile';

/** A point in CSS pixels, measured from the stage's top-left corner. */
export type Point = readonly [x: number, y: number];

/** Label face of one tab on screen: top-left, top-right, bottom-right, bottom-left. */
export type Quad = readonly [Point, Point, Point, Point];

export type TabQuads = Record<SectionId, Quad>;

/** One authored camera, as written by blender/export_book.py. Vectors are in three.js space. */
export interface BookView {
  /** Width over height of the poster frame. */
  aspect: number;
  /** Width over height of the centred region that must always stay on screen. */
  safeAspect: number;
  fovY: number;
  position: [number, number, number];
  quaternion: [number, number, number, number];
  /** Point the camera orbits around for pointer parallax. */
  pivot: [number, number, number];
  /** Poster path relative to the site base. */
  poster: string;
  /** Tab label quads at rest, normalised to the poster frame with y down. */
  tabs: Record<SectionId, number[][]>;
}

export interface BookMeta {
  tabOrder: SectionId[];
  views: Record<ViewId, BookView>;
}
