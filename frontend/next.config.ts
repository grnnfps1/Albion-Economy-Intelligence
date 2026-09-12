import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // O browser nunca fala com o FastAPI diretamente: passa por Route Handlers
  // do Next, que injetam credencial de serviço. Ver docs/00-arquitetura.md §4.
  env: {},
};

export default nextConfig;
