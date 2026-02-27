"use client";

import Image from "next/image";
import Link from "next/link";
import { motion } from "framer-motion";

export function Header() {
  return (
    <header className="flex items-center justify-between py-4 border-b border-border relative header-gradient-line">
      <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
        <motion.div
          initial={{ rotate: -10, opacity: 0 }}
          animate={{ rotate: 0, opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <Image
            src="/riverse_logo.png"
            alt="RIVERSE"
            width={36}
            height={36}
            className="object-contain"
          />
        </motion.div>
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
