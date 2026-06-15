/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API base URL override. Defaults to http://localhost:8000 in dev and
   *  the same-origin /api reverse-proxy in production builds. */
  readonly VITE_API_URL?: string;
}
