import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: false,
  serverExternalPackages: ["pdfjs-dist"],
  experimental: {
    // @ts-expect-error - turbo is valid but types might be outdated
    turbo: {
      resolveAlias: {
        canvas: './empty-module.ts',
      },
    },
  },
  webpack: (config) => {
    config.resolve.alias.canvas = false;
    return config;
  },
};

export default nextConfig;
