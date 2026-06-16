import { defineConfig } from "vite";

export default defineConfig({
  // force a single copy of three — the app, @thatopen/* and camera-controls each
  // depend on it; without this they can resolve to different instances ("Multiple
  // instances of Three.js being imported"), bloating the bundle and breaking
  // instanceof checks across the boundary.
  resolve: {
    dedupe: ["three"],
  },
  // web-ifc and the fragments worker ship their own WASM/worker assets; don't let
  // esbuild's dep pre-bundler rewrite them.
  optimizeDeps: {
    exclude: ["web-ifc", "@thatopen/fragments", "@thatopen/components"],
  },
  server: {
    port: 5173,
    // SharedArrayBuffer (used by web-ifc multithreaded WASM) needs cross-origin isolation.
    headers: {
      "Cross-Origin-Opener-Policy": "same-origin",
      "Cross-Origin-Embedder-Policy": "require-corp",
    },
  },
  build: {
    chunkSizeWarningLimit: 4000,
    rollupOptions: {
      output: {
        // split heavy vendor libs into cacheable chunks (they change far less than app code)
        manualChunks: {
          three: ["three"],
          thatopen: ["@thatopen/components", "@thatopen/components-front", "@thatopen/fragments"],
        },
      },
    },
  },
});
