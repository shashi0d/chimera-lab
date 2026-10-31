import type { Part } from "./types";

/**
 * The body diagram is drawn from this list (U1). Each region is one pinnable part.
 * Adding a part (L2: wings) means one new entry here plus its id in PARTS, not a redraw.
 * Coordinates are in the diagram's 260 × 160 viewBox; the animal faces right.
 */
export interface BodyRegion {
  id: Part;
  /** Visible outline. */
  d: string;
  /** Larger click target when the outline is thin or split (limbs, tail). */
  hit?: string;
  /** Where the part name sits. */
  label: { x: number; y: number };
  /** Centre of the donor portrait badge when the part is pinned. */
  badge: { x: number; y: number };
}

// Paint order matters: later regions sit on top.
export const BODY_REGIONS: BodyRegion[] = [
  {
    id: "tail",
    d: "M72 60 C56 58 40 56 22 44 L16 54 C34 67 54 73 72 73 Z",
    hit: "M14 40 H72 V76 H14 Z",
    label: { x: 30, y: 92 },
    badge: { x: 30, y: 30 },
  },
  {
    id: "limbs",
    d: "M82 92 h13 v42 a4 4 0 0 1 -4 4 h-5 a4 4 0 0 1 -4 -4 Z M104 92 h13 v42 a4 4 0 0 1 -4 4 h-5 a4 4 0 0 1 -4 -4 Z M146 92 h13 v42 a4 4 0 0 1 -4 4 h-5 a4 4 0 0 1 -4 -4 Z M166 92 h13 v42 a4 4 0 0 1 -4 4 h-5 a4 4 0 0 1 -4 -4 Z",
    hit: "M80 101 H181 V140 H80 Z",
    label: { x: 131, y: 154 },
    badge: { x: 204, y: 122 },
  },
  {
    id: "body",
    d: "M92 52 H158 A22 22 0 0 1 180 74 V80 A22 22 0 0 1 158 102 H92 A22 22 0 0 1 70 80 V74 A22 22 0 0 1 92 52 Z",
    label: { x: 125, y: 86 },
    badge: { x: 92, y: 80 },
  },
  {
    id: "covering",
    d: "M90 47 H162 A7 7 0 0 1 162 61 H90 A7 7 0 0 1 90 47 Z",
    hit: "M84 30 H168 V62 H84 Z",
    label: { x: 126, y: 40 },
    badge: { x: 178, y: 36 },
  },
  {
    id: "head",
    d: "M206 26 C222 26 234 38 234 50 C234 62 222 72 208 72 C194 72 182 62 182 50 C182 38 192 26 206 26 Z",
    label: { x: 208, y: 54 },
    badge: { x: 240, y: 22 },
  },
];
