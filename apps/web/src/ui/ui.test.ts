import { describe, expect, it } from "vitest";

import { escapeHtml } from "./feedback";
import { noProjectHtml } from "./empty";

describe("escapeHtml (stored-XSS guard)", () => {
  it("escapes the HTML-significant characters", () => {
    expect(escapeHtml(`<img src=x onerror="alert(1)">`))
      .toBe("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;");
    expect(escapeHtml(`a & b ' c`)).toBe("a &amp; b &#39; c");
  });
  it("coerces null/undefined/numbers to a safe string", () => {
    expect(escapeHtml(null)).toBe("");
    expect(escapeHtml(undefined)).toBe("");
    expect(escapeHtml(42)).toBe("42");
  });
  it("neutralizes a script payload (no raw < or >)", () => {
    const out = escapeHtml("</script><script>steal()</script>");
    expect(out.includes("<")).toBe(false);
    expect(out.includes(">")).toBe(false);
  });
});

describe("noProjectHtml (demo-aware empty state)", () => {
  // VITE_PAGES is unset under vitest → the real-app branch
  it("gives an actionable create/open hint in the full app", () => {
    const html = noProjectHtml("the GC portal");
    expect(html).toContain("No project open");
    expect(html).toContain("＋ New");
    expect(html).toContain("the GC portal");
  });
});
