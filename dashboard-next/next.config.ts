import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "cdn-img.piccoma.com" },
      { protocol: "https", hostname: "obs.line-scdn.net" },
      { protocol: "https", hostname: "**.cmoa.jp" },
      { protocol: "https", hostname: "mechacomic.jp" },
      { protocol: "https", hostname: "www.asuratoon.com" },
      { protocol: "https", hostname: "**.asuracomic.net" },
      { protocol: "https", hostname: "**.asurascans.com" },
    ],
  },
  poweredByHeader: false,
};

export default nextConfig;
