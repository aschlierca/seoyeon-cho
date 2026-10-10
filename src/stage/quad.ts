import type { SectionId } from '../sections';
import type { BookView, Point, Quad, TabQuads } from './types';

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Where a view's poster frame lands inside the stage box. The frame is as tall as
 * the stage unless the stage is narrower than the safe area, in which case it
 * shrinks to fit the safe area's width. Book.module.css sizes the poster with the
 * same rule, and BookStage sizes the camera with it, so all three line up.
 */
export function frameRect(stageWidth: number, stageHeight: number, view: BookView): Rect {
  const height = Math.min(stageHeight, stageWidth / view.safeAspect);
  const width = height * view.aspect;
  return { x: (stageWidth - width) / 2, y: (stageHeight - height) / 2, width, height };
}

/** Tab quads at rest, taken from the exported metadata. Needs no WebGL. */
export function restQuads(view: BookView, stageWidth: number, stageHeight: number): TabQuads {
  const rect = frameRect(stageWidth, stageHeight, view);
  const quads = {} as Record<SectionId, Quad>;
  for (const [id, corners] of Object.entries(view.tabs) as [SectionId, number[][]][]) {
    quads[id] = corners.map(([x, y]) => [rect.x + x * rect.width, rect.y + y * rect.height] as Point) as unknown as Quad;
  }
  return quads;
}

function distance(a: Point, b: Point): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

/** Natural label size for a quad: the mean of its opposite edges. */
export function quadSize(quad: Quad): { width: number; height: number } {
  const [tl, tr, br, bl] = quad;
  return {
    width: (distance(tl, tr) + distance(bl, br)) / 2,
    height: (distance(tl, bl) + distance(tr, br)) / 2,
  };
}

type Matrix3 = number[];

function adjugate(m: Matrix3): Matrix3 {
  return [
    m[4] * m[8] - m[5] * m[7], m[2] * m[7] - m[1] * m[8], m[1] * m[5] - m[2] * m[4],
    m[5] * m[6] - m[3] * m[8], m[0] * m[8] - m[2] * m[6], m[2] * m[3] - m[0] * m[5],
    m[3] * m[7] - m[4] * m[6], m[1] * m[6] - m[0] * m[7], m[0] * m[4] - m[1] * m[3],
  ];
}

function multiply(a: Matrix3, b: Matrix3): Matrix3 {
  const out = new Array<number>(9);
  for (let row = 0; row < 3; row++) {
    for (let column = 0; column < 3; column++) {
      out[3 * row + column] = a[3 * row] * b[column] + a[3 * row + 1] * b[3 + column] + a[3 * row + 2] * b[6 + column];
    }
  }
  return out;
}

function basisToPoints(p1: Point, p2: Point, p3: Point, p4: Point): Matrix3 {
  const m = [p1[0], p2[0], p3[0], p1[1], p2[1], p3[1], 1, 1, 1];
  const a = adjugate(m);
  const v = [
    a[0] * p4[0] + a[1] * p4[1] + a[2],
    a[3] * p4[0] + a[4] * p4[1] + a[5],
    a[6] * p4[0] + a[7] * p4[1] + a[8],
  ];
  return multiply(m, [v[0], 0, 0, 0, v[1], 0, 0, 0, v[2]]);
}

/**
 * CSS transform that maps a width x height box (transform-origin 0 0) onto a
 * screen quad, perspective included. This is what lets real link text sit on the
 * face of a 3D tab.
 */
export function quadToMatrix3d(width: number, height: number, quad: Quad): string {
  const [tl, tr, br, bl] = quad;
  const source = basisToPoints([0, 0], [width, 0], [0, height], [width, height]);
  const target = basisToPoints(tl, tr, bl, br);
  const t = multiply(target, adjugate(source)).map((value, _, all) => value / all[8]);
  return `matrix3d(${t[0]},${t[3]},0,${t[6]},${t[1]},${t[4]},0,${t[7]},0,0,1,0,${t[2]},${t[5]},0,1)`;
}
