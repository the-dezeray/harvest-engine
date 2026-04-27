import type { NextConfig } from "next";

const ML_BASE = process.env.ML_SERVICE_URL ?? "http://localhost:8001";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/ml-api/:path*",
        destination: `${ML_BASE}/:path*`,
      },
    ];
  },
};

export default nextConfig;
