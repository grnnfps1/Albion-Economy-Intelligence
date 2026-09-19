import path from "node:path";

import { defineConfig } from "vitest/config";

export default defineConfig({
  // O `@/` do tsconfig precisa existir aqui também: o Vitest não lê `paths` do
  // TypeScript, e sem isto qualquer teste que toque num módulo com import
  // absoluto falha na resolução — não no comportamento.
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
