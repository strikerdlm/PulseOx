/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  swcMinify: true,
  experimental: {
    optimizePackageImports: ['echarts', 'echarts-for-react', 'lucide-react'],
  },
};

module.exports = nextConfig;
