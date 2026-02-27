"use client";

import { useEffect, useState } from "react";
import { useReducedMotion } from "framer-motion";

export function useCountUp(
  target: number,
  duration: number = 600,
  delay: number = 0
): number {
  const prefersReducedMotion = useReducedMotion();
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (prefersReducedMotion) {
      setValue(target);
      return;
    }

    const timeout = setTimeout(() => {
      const startTime = performance.now();
      const animate = (now: number) => {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        setValue(Math.round(eased * target));
        if (progress < 1) {
          requestAnimationFrame(animate);
        }
      };
      requestAnimationFrame(animate);
    }, delay);

    return () => clearTimeout(timeout);
  }, [target, duration, delay, prefersReducedMotion]);

  return value;
}
