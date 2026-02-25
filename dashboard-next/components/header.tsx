"use client";

import Image from "next/image";
import Link from "next/link";

export function Header() {
  return (
    <header className="flex items-center justify-between py-4 border-b border-border">
      <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
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
      </Link>
      <Link
        href="/search"
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors px-3 py-1.5 rounded-lg hover:bg-muted"
      >
        🔍 작품 검색
      </Link>
    </header>
  );
}
