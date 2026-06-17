import { describe, expect, it } from "vitest";

import { fromLocalIds, merge, single } from "./modelIds";

describe("modelIds", () => {
  it("single() wraps one localId in a per-model set", () => {
    const m = single("modelA", 42);
    expect(Object.keys(m)).toEqual(["modelA"]);
    expect([...m.modelA]).toEqual([42]);
  });

  it("fromLocalIds() builds a set and dedupes", () => {
    const m = fromLocalIds("modelA", [1, 2, 2, 3]);
    expect([...m.modelA].sort((a, b) => a - b)).toEqual([1, 2, 3]);
  });

  it("merge() unions ids within a model", () => {
    const m = merge(single("a", 1), fromLocalIds("a", [2, 3]));
    expect([...m.a].sort((x, y) => x - y)).toEqual([1, 2, 3]);
  });

  it("merge() keeps separate models separate", () => {
    const m = merge(single("a", 1), single("b", 9));
    expect(Object.keys(m).sort()).toEqual(["a", "b"]);
    expect([...m.a]).toEqual([1]);
    expect([...m.b]).toEqual([9]);
  });

  it("merge() of nothing is an empty map", () => {
    expect(merge()).toEqual({});
  });
});
