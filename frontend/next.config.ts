import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // CRITICAL: Enable standalone output for Lambda compatibility
  output: 'standalone',

  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'res.cloudinary.com',
        pathname: '/topmate/**',
      },
    ],
    // Lambda-specific: Disable image optimization (use external service or S3)
    unoptimized: process.env.DISABLE_IMAGE_OPTIMIZATION === 'true',
  },
};

export default nextConfig;
