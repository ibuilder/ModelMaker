/** @vitest-environment happy-dom */
// End-to-end stored-XSS lock: a connection whose NAME is an injection payload must render as inert
// text, never as live DOM. Guards the escapeHtml() fix in the connections admin modal.
import { afterEach, describe, expect, it } from "vitest";

import { openConnectionsModal } from "./connectionsUI";
import type { ApiClient } from "../api/client";

const PAYLOAD = `<img src=x onerror="alert(1)">`;
const stubApi = {
  connections: async () => ({ types: ["postgres"], connections: [
    { id: "c1", name: PAYLOAD, type: "postgres", builtin: false, status: null },
  ] }),
} as unknown as ApiClient;

afterEach(() => { document.body.innerHTML = ""; });

describe("connections modal — XSS escaping", () => {
  it("renders a malicious connection name as inert text, not live DOM", async () => {
    openConnectionsModal(stubApi, () => null);
    await new Promise((r) => setTimeout(r, 0));   // let the async render() resolve
    // the payload must NOT have created a real <img> element anywhere in the modal
    expect(document.querySelectorAll("img").length).toBe(0);
    // the escaped payload should appear as literal text content
    expect(document.body.textContent).toContain(PAYLOAD);
    // and the raw, unescaped tag must not be present in the markup
    expect(document.body.innerHTML.includes("<img")).toBe(false);
  });
});
