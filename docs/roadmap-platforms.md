# Roadmap — Multi-platform packaging (web, Windows, macOS, iOS, Android)

Goal: ship the viewer + data platform beyond the browser to desktop and mobile, **without
forking the codebase**. The web app (`apps/web`, Vite + TS + Three.js + Fragments) stays the
single UI source; native targets wrap it.

## Current state
- **Web — done.** Vite/TS SPA served by nginx in the Docker stack; runs fully offline with
  local WASM (web-ifc) and self-hosted Fragments tiles (per CLAUDE.md). This is the canonical
  build everything else wraps.

## Strategy: one web core, thin native shells
| Target | Wrapper | Notes |
|--------|---------|-------|
| Web (PWA) | Vite build + service worker | Add a manifest + offline cache so it's installable; closest to "native" with least effort. **Do this first.** |
| Windows / macOS / Linux | **Tauri** (preferred) or Electron | Tauri = tiny Rust shell, system WebView, ~10MB vs Electron's bundled Chromium. Gives native file dialogs for Open/Save (.ifc/.frag), local cache dir, offline WASM. |
| iOS / Android | **Capacitor** | Wraps the same web build in a native WebView; plugins for filesystem, share sheet, camera (site photos → punchlist/BCF). PWA is the fallback if app-store distribution isn't needed. |

Why not React Native / Flutter: would require rewriting the Three.js/Fragments viewer. The
WebView-wrapper path preserves the entire existing renderer and tool set.

## Phasing
1. **PWA hardening** — manifest, installability, service-worker caching of WASM + tiles +
   app shell; verify true offline. Unlocks "install" on every platform immediately.
2. **Tauri desktop** — wrap the build; wire native Open/Save dialogs to the existing
   Open ▾ / Save ▾ menus (replace the hidden `<input type=file>` with Tauri's `dialog` +
   `fs` APIs); bundle the local converter cache. Sign + notarize (Win Authenticode, macOS
   notarization).
3. **Capacitor mobile** — same build; add filesystem + share plugins; tune the responsive
   layout (already has an 820px breakpoint) for touch; on-site photo capture into BCF topics.
4. **Backend** — the FastAPI + Postgres + MinIO stack stays server-side (cloud or on-prem);
   native apps talk to it over HTTPS, or run a bundled local API for fully-offline desktop.

## Performance / offline notes
- Mega-model streaming (range-served .frag) must work over the WebView fetch stack — verify
  range requests on iOS WKWebView (historically finicky).
- WASM (web-ifc) must load from the bundle, not a CDN, to keep the offline guarantee.
- Keep geometry (.frag stream) and metadata (API) separate on every platform.

## "Claude remote" / background agents for native work
Desktop/mobile packaging is long-running, environment-specific (Xcode/macOS for iOS, Android
SDK, code-signing certs) and parallelizable across targets — a good fit for **background /
remote agents**: spin up per-platform build agents (Tauri-Windows, Tauri-macOS, Capacitor-iOS,
Capacitor-Android) that own their toolchain and CI, reporting back. Track each as its own
task/worktree so they don't block the main web line. Native signing secrets and store
credentials are **user-performed steps** (never automated): the agent prepares the build, the
user supplies certs and submits to the stores.
