import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The local dashboard is commonly opened at 127.0.0.1:3000. Allow its
  // browser origin to fetch Next's development-only HMR resources.
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
