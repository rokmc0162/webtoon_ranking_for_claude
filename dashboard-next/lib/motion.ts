import type { Variants, Transition } from "framer-motion";

// ── Shared Transitions ──────────────────────────
export const springBouncy: Transition = {
  type: "spring",
  stiffness: 300,
  damping: 20,
};

// ── Page-level stagger container ────────────────
export const staggerContainer: Variants = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.1,
    },
  },
};

// ── Fade-in + Slide-up (for staggered children) ─
export const fadeSlideUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: "easeOut" },
  },
};

// ── Table row stagger container ─────────────────
export const tableContainer: Variants = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.03,
      delayChildren: 0.05,
    },
  },
};

// ── Table row entrance ──────────────────────────
export const tableRowVariant: Variants = {
  hidden: { opacity: 0, x: -12 },
  show: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.3, ease: "easeOut" },
  },
};

// ── Scale pop (for rank badges) ─────────────────
export const scalePop: Variants = {
  hidden: { opacity: 0, scale: 0.5 },
  show: {
    opacity: 1,
    scale: 1,
    transition: springBouncy,
  },
};

// ── Content swap (platform/genre change) ────────
export const contentSwap: Variants = {
  enter: { opacity: 0, y: 8 },
  center: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.25, ease: "easeOut" },
  },
  exit: {
    opacity: 0,
    y: -8,
    transition: { duration: 0.15, ease: "easeIn" },
  },
};
