"use client";

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
          <button
            key={g.key}
            onClick={() => onSelect(g.key)}
            className={cn(
              "px-3 py-1 rounded-full text-xs sm:text-sm font-medium transition-all cursor-pointer",
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
          >
            {g.label}
            {rCount > 0 && (
              <span className={cn("ml-1", isActive ? "text-white/80" : "text-primary font-bold")}>
                ({rCount})
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
