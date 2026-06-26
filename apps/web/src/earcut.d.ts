declare module "earcut" {
  /** Triangulate a flat coordinate array; returns triangle vertex indices. */
  export default function earcut(
    data: ArrayLike<number>,
    holeIndices?: ArrayLike<number> | null,
    dim?: number,
  ): number[];
}
