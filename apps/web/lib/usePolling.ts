"use client";

import { useEffect, useRef } from "react";

/** Run `fn` immediately and then on an interval. Pauses while the tab is hidden. */
export function usePolling(fn: () => void, ms: number) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    ref.current();
    const id = setInterval(() => {
      if (typeof document === "undefined" || document.visibilityState === "visible") {
        ref.current();
      }
    }, ms);
    return () => clearInterval(id);
  }, [ms]);
}
