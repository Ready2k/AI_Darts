// Shared geometry for the broadcast board: board-mm ↔ SVG pixel space.
export const SIZE = 500
export const C = SIZE / 2
export const SCALE = 1.2 // px per mm — double ring (170mm) lands at r=204px

// Board-mm → percentage position inside the SVG (for zoom transform origins).
export function mmToPct([x, y]) {
  return [((C + x * SCALE) / SIZE) * 100, ((C - y * SCALE) / SIZE) * 100]
}
