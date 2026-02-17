"use client";

import Image from "next/image";

export function Header() {
  return (
    <header className="flex items-center justify-center gap-3 py-4 border-b border-border">
      <Image
        src="/riverse_logo.png"
        alt="RIVERSE"
        width={36}
        height={36}
        className="object-contain"
      />
      <h1 className="text-xl font-bold text-primary">
        일본 랭킹 아카이브
      </h1>
    </header>
  );
}
