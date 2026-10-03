"use client";

import { useEffect, useRef, useState } from "react";

/**
 * The rendered width of an element, so charts are drawn in real pixels and
 * their text stays readable on a phone instead of shrinking with a viewBox.
 * Falls back to `fallback` where layout is not measured (tests, first render).
 */
export function useWidth<T extends HTMLElement>(fallback = 360) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const w = Math.floor(el.getBoundingClientRect().width);
      if (w > 0) setWidth(w);
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return { ref, width };
}

/** A round axis maximum (1, 2, 2.5 or 5 x 10^n) at or above `value`. */
export function niceMax(value: number): number {
  if (!(value > 0)) return 1;
  const exp = Math.floor(Math.log10(value));
  const base = 10 ** exp;
  for (const step of [1, 2, 2.5, 5, 10]) {
    if (step * base >= value) return step * base;
  }
  return 10 * base;
}

/** Round tick values (1, 2, 2.5 or 5 x 10^n apart) covering [min, max]. */
export function niceTicks(min: number, max: number, target = 5): number[] {
  const raw = (max - min) / target || 1;
  const exp = Math.floor(Math.log10(raw));
  const base = 10 ** exp;
  const step = [1, 2, 2.5, 5, 10].map((m) => m * base).find((s) => s >= raw) ?? 10 * base;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(v);
  return out;
}

/** Evenly spaced ticks from min to max inclusive. */
export function ticks(min: number, max: number, count = 5): number[] {
  const out: number[] = [];
  for (let i = 0; i <= count; i += 1) out.push(min + ((max - min) * i) / count);
  return out;
}
