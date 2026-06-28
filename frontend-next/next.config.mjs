const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://127.0.0.1:8001/api/:path*" },
      { source: "/health",     destination: "http://127.0.0.1:8001/health" },
      { source: "/metrics",   destination: "http://127.0.0.1:8001/metrics" },
      { source: "/openapi.json", destination: "http://127.0.0.1:8001/openapi.json" },
    ];
  },
};

export default nextConfig;
