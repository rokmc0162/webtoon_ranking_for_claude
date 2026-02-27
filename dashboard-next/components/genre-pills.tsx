"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { Genre } from "@/lib/types";

interface GenrePillsProps {
  genres: Genre[];
  selected: string;
  onSelect: (key: string) => void;
  platformColor: string;
  riverseCounts: Record<string, number>;
}

export function GenrePills({
  genres,
  selected,
  onSelect,
  platformColor,
  riverseCounts,
}: GenrePillsProps) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {genres.map((g) => {
        const isActive = selected === g.key;
        const rCount = riverseCounts[g.key] || 0;
        return (
          <motion.button
            key={g.key}
            onClick={() => onSelect(g.key)}
            className={cn(
              "relative px-3 py-1 rounded-full text-xs sm:text-sm font-medium cursor-pointer",
              "border",
              isActive
                ? "text-white border-transparent"
                : "border-border text-muted-foreground hover:bg-muted"
            )}
            style={
              isActive
                ? { backgroundColor: platformColor, borderColor: platformColor }
                : undefined
            }
            whileTap={{ scale: 0.95 }}
          >
            {isActive && (
              <motion.div
                layoutId="genre-active-pill"
                className="absolute inset-0 rounded-full"
                style={{ backgroundColor: platformColor }}
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
              />
            )}
            <span className="relative z-10">
              {g.label}
              {rCount > 0 && (
                <span className={cn("ml-1", isActive ? "text-white/80" : "text-primary font-bold")}>
                  ({rCount})
                </span>
              )}
            </span>
          </motion.button>
        );
      })}
    </div>
  );
}
