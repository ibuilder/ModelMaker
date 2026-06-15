/** Lightweight UX feedback: transient toasts + a loading overlay. No dependencies. */

let toastHost: HTMLElement | null = null;

function host(): HTMLElement {
  if (!toastHost) {
    toastHost = document.createElement("div");
    toastHost.className = "toast-host";
    document.body.appendChild(toastHost);
  }
  return toastHost;
}

export type ToastKind = "info" | "success" | "error";

export function toast(message: string, kind: ToastKind = "info", ms = 3200): void {
  const el = document.createElement("div");
  el.className = `toast toast-${kind}`;
  el.textContent = message;
  host().appendChild(el);
  // animate in
  requestAnimationFrame(() => el.classList.add("show"));
  const remove = () => {
    el.classList.remove("show");
    el.addEventListener("transitionend", () => el.remove(), { once: true });
    setTimeout(() => el.remove(), 400);
  };
  el.onclick = remove;
  if (ms > 0) setTimeout(remove, ms);
}

// --- loading overlay (one global, scoped to the viewer container) ------------
let overlay: HTMLElement | null = null;
let depth = 0;

function ensureOverlay(container: HTMLElement): HTMLElement {
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.className = "loading-overlay";
    overlay.innerHTML = `<div class="spinner"></div><div class="loading-label"></div>`;
    container.appendChild(overlay);
  }
  return overlay;
}

/** Run an async task with a loading overlay + label; toasts on failure. Returns the result. */
export async function withLoading<T>(container: HTMLElement, label: string,
                                     task: () => Promise<T>): Promise<T | undefined> {
  const ov = ensureOverlay(container);
  (ov.querySelector(".loading-label") as HTMLElement).textContent = label;
  depth++;
  ov.classList.add("show");
  try {
    return await task();
  } catch (err) {
    toast(`${label} failed: ${(err as Error).message}`, "error", 5000);
    return undefined;
  } finally {
    if (--depth <= 0) ov.classList.remove("show");
  }
}
