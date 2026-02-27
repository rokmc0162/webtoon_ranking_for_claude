"use client";

import { motion } from "framer-motion";

interface RankChangeProps {
  change: number;
}

export function RankChange({ change }: RankChangeProps) {
  if (change === 999) {
    return (
      <motion.span
        className="inline-block bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full text-xs font-bold"
        animate={{
          scale: [1, 1.08, 1],
          opacity: [1, 0.85, 1],
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      >
        NEW
      </motion.span>
    );
  }

  if (change > 0) {
    return (
      <motion.span
        className="text-red-500 font-semibold text-sm"
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.2 }}
      >
        ▲{change}
      </motion.span>
    );
  }

  if (change < 0) {
    return (
      <motion.span
        className="text-blue-500 font-semibold text-sm"
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.2 }}
      >
        ▼{Math.abs(change)}
      </motion.span>
    );
  }

  return <span className="text-muted-foreground">—</span>;
}
