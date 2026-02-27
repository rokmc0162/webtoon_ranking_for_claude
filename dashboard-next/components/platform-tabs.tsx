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
    <div className="flex flex-wrap gap-2 sm:gap-3 justify-center">
      {PLATFORMS.map((p) => {
        const isActive = selected === p.id;
        return (
          <button
            key={p.id}
            onClick={() => onSelect(p.id)}
            title={p.name}
            className={cn(
              "rounded-2xl p-1.5 sm:p-2 transition-all cursor-pointer",
              "border-2 hover:shadow-md hover:scale-105",
              isActive
                ? "shadow-lg scale-105"
                : "border-transparent bg-white hover:bg-muted"
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
            {p.logo ? (
              <Image
                src={p.logo}
                alt={p.name}
                width={56}
                height={56}
                className="rounded-xl object-contain w-11 h-11 sm:w-14 sm:h-14"
              />
            ) : (
              <div
                className="rounded-xl w-11 h-11 sm:w-14 sm:h-14 flex items-center justify-center text-white font-bold text-xl"
                style={{ backgroundColor: p.color }}
              >
                {p.name.charAt(0)}
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}
