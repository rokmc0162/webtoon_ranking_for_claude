"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { scalePop } from "@/lib/motion";

interface RankBadgeProps {
  rank: number;
  platformColor: string;
}

export function RankBadge({ rank, platformColor }: RankBadgeProps) {
  if (rank <= 3) {
    return (
      <motion.span
        variants={scalePop}
        className="inline-flex items-center justify-center w-8 h-8 rounded-full text-white text-sm font-bold"
        style={{ backgroundColor: platformColor }}
      >
        {rank}
      </motion.span>
    );
  }

  if (rank <= 10) {
    return (
      <span
        className={cn(
          "inline-flex items-center justify-center w-8 h-8 rounded-full",
          "bg-muted text-foreground text-sm font-semibold"
        )}
      >
        {rank}
      </span>
    );
  }

  return (
    <span className="text-muted-foreground font-medium text-sm">
      {rank}
    </span>
  );
}
