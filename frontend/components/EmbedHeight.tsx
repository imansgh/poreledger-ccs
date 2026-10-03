"use client";

import { useEffect } from "react";

/** Message the host page receives: ``{type, height}`` in CSS pixels. */
export const EMBED_MESSAGE_TYPE = "poreledger-ccs:height";

/**
 * Parent origins allowed to receive the height message (BUILD-TIME
 * ``NEXT_PUBLIC_CCS_EMBED_ORIGINS``, comma-separated origins).
 */
export function embedOrigins(): string[] {
  const raw = process.env.NEXT_PUBLIC_CCS_EMBED_ORIGINS ?? "";
  return raw
    .split(",")
    .map((o) => o.trim())
    // https only; plain http only on loopback, for local embedding tests (the
    // publication build rejects any loopback URL in the bundle).
    .filter((o) => /^https:\/\/[A-Za-z0-9.-]+(:\d+)?$/.test(o) ||
                   /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(o));
}

/**
 * When the demo runs inside an iframe on an allowed site, report the page
 * height so the host can size the frame (no scrollbar inside a scrollbar).
 * Only the height is sent, only to the named origins; nothing when the page
 * is not framed.
 */
export function EmbedHeight() {
  useEffect(() => {
    const origins = embedOrigins();
    if (!origins.length || window.parent === window) return;
    let last = -1;
    const report = () => {
      const height = Math.ceil(document.documentElement.scrollHeight);
      if (height === last) return;
      last = height;
      for (const origin of origins) {
        window.parent.postMessage({ type: EMBED_MESSAGE_TYPE, height }, origin);
      }
    };
    report();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(report);
    observer.observe(document.body);
    return () => observer.disconnect();
  }, []);
  return null;
}
