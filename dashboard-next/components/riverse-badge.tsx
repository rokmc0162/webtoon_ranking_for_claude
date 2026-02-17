"use client";

import Image from "next/image";

export function RiverseBadge() {
  return (
    <Image
      src="/riverse_logo.png"
      alt="RIVERSE"
      width={14}
      height={14}
      className="inline-block ml-1 align-middle opacity-85"
    />
  );
}
