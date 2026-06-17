import { defineConfig } from "vitest/config";

// Standalone from vite.config.ts so the PWA/coi plugins don't run under test. happy-dom gives
// the unit tests a lightweight DOM + localStorage without a real browser.
export default defineConfig({
  test: {
    environment: "happy-dom",
    include: ["src/**/*.test.ts"],
    globals: true,
  },
});
