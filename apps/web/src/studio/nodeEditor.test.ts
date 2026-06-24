/** @vitest-environment happy-dom */
// Per-file DOM environment (the other web tests are pure/node). A smoke test for the Studio node
// editor — the largest previously-untested web module — driven entirely through the DOM the way a
// user does: mount → palette → add → wire ports → Run → results, plus clear + empty-state.
import { beforeEach, describe, expect, it } from "vitest";

import { NodeEditor } from "./nodeEditor";
import type { ApiClient, ComputeGraph } from "../api/client";

// minimal ApiClient stub: two nodes (A.y → B.y), runGraph echoes a fixed result per node
const stubApi = {
  computeNodes: async () => ({
    nodes: [
      { key: "a", label: "Node A", category: "Generative", doc: "", inputs: [{ name: "x", default: 1 }], outputs: ["y"] },
      { key: "b", label: "Node B", category: "Finance", doc: "", inputs: [{ name: "y", default: 0 }], outputs: ["z"] },
    ],
  }),
  runGraph: async (g: ComputeGraph) => ({
    order: g.nodes.map((n) => n.id),
    results: Object.fromEntries(g.nodes.map((n) => [n.id, { y: 42, z: 7 }])),
    node_count: g.nodes.length,
  }),
} as unknown as ApiClient;

function mountEditor() {
  const root = document.createElement("div");
  document.body.appendChild(root);
  return new NodeEditor(root, stubApi);
}

describe("Studio NodeEditor", () => {
  beforeEach(() => { localStorage.clear(); document.body.innerHTML = ""; });

  it("loads the palette and shows an empty-state hint", async () => {
    const ed = mountEditor();
    await ed.mount();
    const root = document.body.firstElementChild!;
    expect(root.querySelectorAll(".studio-pal-node").length).toBe(2);     // two node types
    expect(root.querySelector(".studio-empty")).toBeTruthy();             // empty canvas hint
  });

  it("adds nodes from the palette and clears the empty state", async () => {
    const ed = mountEditor(); await ed.mount();
    const root = document.body.firstElementChild!;
    (root.querySelectorAll(".studio-pal-node")[0] as HTMLElement).click();
    expect(root.querySelectorAll(".studio-node").length).toBe(1);
    expect(root.querySelector(".studio-empty")).toBeFalsy();              // hint gone once a node exists
    (root.querySelectorAll(".studio-pal-node")[1] as HTMLElement).click();
    expect(root.querySelectorAll(".studio-node").length).toBe(2);
  });

  it("wires an output into an input (click-to-connect) and runs the graph", async () => {
    const ed = mountEditor(); await ed.mount();
    const root = document.body.firstElementChild!;
    (root.querySelectorAll(".studio-pal-node")[0] as HTMLElement).click();  // n1 (A, out y)
    (root.querySelectorAll(".studio-pal-node")[1] as HTMLElement).click();  // n2 (B, in y)
    // click output dot of n1, then input dot of n2 → one edge
    (root.querySelector("#dot-n1-out-y") as HTMLElement).click();
    (root.querySelector("#dot-n2-in-y") as HTMLElement).click();
    expect(root.querySelectorAll(".studio-edge").length).toBe(1);
    // a wired input is disabled (driven by the upstream port, not a manual param)
    const n2field = root.querySelector('.studio-node[data-id="n2"] .studio-field') as HTMLInputElement;
    expect(n2field.disabled).toBe(true);
    // Run → results fill the output value cells
    (root.querySelector("#studio-run") as HTMLElement).click();
    await new Promise((r) => setTimeout(r, 0));
    const vals = [...root.querySelectorAll(".studio-out-val")].map((e) => e.textContent);
    expect(vals.some((v) => v === "42")).toBe(true);
  });

  it("clear() empties the graph and restores the hint; graph persists to localStorage", async () => {
    const ed = mountEditor(); await ed.mount();
    const root = document.body.firstElementChild!;
    (root.querySelectorAll(".studio-pal-node")[0] as HTMLElement).click();
    expect(localStorage.getItem("studio-graph-v1")).toContain('"type":"a"');   // persisted on add
    (root.querySelector("#studio-clear") as HTMLElement).click();
    expect(root.querySelectorAll(".studio-node").length).toBe(0);
    expect(root.querySelector(".studio-empty")).toBeTruthy();
  });
});
