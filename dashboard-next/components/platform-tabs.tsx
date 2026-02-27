"use client";

import Image from "next/image";
import { motion } from "framer-motion";
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
          <motion.button
            key={p.id}
            onClick={() => onSelect(p.id)}
            title={p.name}
            className={cn(
              "relative rounded-2xl p-1.5 sm:p-2 cursor-pointer",
              "border-2",
              isActive
                ? "shadow-lg"
                : "border-transparent bg-white hover:bg-muted"
            )}
            style={
              isActive
                ? {
                    borderColor: p.color,
                    backgroundColor: p.color + "12",
                  }
                : undefined
            }
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.95 }}
            transition={{ type: "spring", stiffness: 400, damping: 25 }}
          >
            {isActive && (
              <motion.div
                layoutId="platform-active-indicator"
                className="absolute inset-0 rounded-2xl"
                style={{ boxShadow: `0 4px 16px ${p.color}40` }}
                transition={{ type: "spring", stiffness: 350, damping: 30 }}
              />
            )}
            {p.logo ? (
              <Image
                src={p.logo}
                alt={p.name}
                width={56}
                height={56}
                className="relative z-10 rounded-xl object-contain w-11 h-11 sm:w-14 sm:h-14"
              />
            ) : (
              <div
                className="relative z-10 rounded-xl w-11 h-11 sm:w-14 sm:h-14 flex items-center justify-center text-white font-bold text-xl"
                style={{ backgroundColor: p.color }}
              >
                {p.name.charAt(0)}
              </div>
            )}
          </motion.button>
        );
      })}
    </div>
  );
}
