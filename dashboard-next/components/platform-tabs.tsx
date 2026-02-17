"use client";

import Image from "next/image";
import { cn } from "@/lib/utils";
import { PLATFORMS } from "@/lib/constants";
import type { PlatformStats } from "@/lib/types";

interface PlatformTabsProps {
  selected: string;
  onSelect: (id: string) => void;
  stats: Record<string, PlatformStats>;
}

export function PlatformTabs({ selected, onSelect, stats }: PlatformTabsProps) {
  return (
    <div className="grid grid-cols-4 gap-2 sm:gap-3">
      {PLATFORMS.map((p) => {
        const isActive = selected === p.id;
        const stat = stats[p.id];
        return (
          <button
            key={p.id}
            onClick={() => onSelect(p.id)}
            className={cn(
              "flex flex-col items-center gap-1.5 rounded-xl p-3 transition-all cursor-pointer",
              "border-2 hover:shadow-md",
              isActive
                ? "shadow-lg"
                : "border-border bg-white hover:bg-muted"
            )}
            style={
              isActive
                ? {
                    borderColor: p.color,
                    backgroundColor: p.color + "12",
                    boxShadow: `0 4px 16px ${p.color}40`,
                  }
                : undefined
            }
          >
            <Image
              src={p.logo}
              alt={p.name}
              width={48}
              height={48}
              className="rounded-xl object-cover w-10 h-10 sm:w-12 sm:h-12"
            />
            <span
              className={cn(
                "text-xs sm:text-sm font-bold",
                !isActive && "text-foreground"
              )}
              style={isActive ? { color: p.color } : undefined}
            >
              {p.name}
            </span>
          </button>
        );
      })}
    </div>
  );
}
