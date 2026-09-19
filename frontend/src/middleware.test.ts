import { beforeEach, describe, expect, it, vi } from "vitest";

import { middleware } from "./middleware";
import { assinar } from "./lib/session";

/**
 * O portão, e o desvio de desenvolvimento.
 *
 * Estes testes cobrem a **lógica**. A garantia mais forte do desvio não é
 * testável aqui e é de outra natureza: `process.env.NODE_ENV` vira literal no
 * build, e `next build` compila com `"production"`, então o bloco inteiro é
 * eliminado do artefato publicado. Isso se confere grepando o `.next`, e está
 * registrado em `docs/06-seguranca.md`.
 *
 * Aqui o `NODE_ENV` é uma variável de verdade, que o teste troca à vontade — o
 * que é exatamente o cenário que **não** existe em produção.
 */
const SEGREDO = "segredo-de-teste-com-tamanho-suficiente-para-hmac";

function pedido(caminho: string, cookie?: string) {
  return {
    nextUrl: new URL(`http://localhost:3000${caminho}`),
    url: `http://localhost:3000${caminho}`,
    cookies: { get: (nome: string) => (cookie ? { name: nome, value: cookie } : undefined) },
    // biome-ignore lint: o middleware só usa estes três campos.
  } as never;
}

beforeEach(() => {
  vi.unstubAllEnvs();
  vi.stubEnv("SESSION_SECRET", SEGREDO);
  vi.stubEnv("DISCORD_CLIENT_ID", "123");
  vi.stubEnv("DEV_AUTH_BYPASS", "");
});

describe("o portão fecha por padrão", () => {
  it("sem cookie, manda para o login e guarda o destino", async () => {
    const r = await middleware(pedido("/crafting/calculadora"));
    expect(r.status).toBe(307);
    expect(r.headers.get("location")).toContain("/login?de=%2Fcrafting%2Fcalculadora");
  });

  it("com sessão válida, deixa passar", async () => {
    const token = await assinar(
      { id: "7", username: "g", avatar: null, iat: Math.floor(Date.now() / 1000) },
      SEGREDO,
    );
    const r = await middleware(pedido("/crafting/calculadora", token));
    expect(r.headers.get("location")).toBeNull();
  });

  it("rota pública passa sem sessão", async () => {
    const r = await middleware(pedido("/login"));
    expect(r.headers.get("location")).toBeNull();
  });

  it("sem SESSION_SECRET a aplicação roda aberta — é o modo local de sempre", async () => {
    vi.stubEnv("SESSION_SECRET", "");
    const r = await middleware(pedido("/crafting/calculadora"));
    expect(r.headers.get("location")).toBeNull();
  });
});

describe("o desvio de desenvolvimento exige as duas condições", () => {
  it("liga com NODE_ENV=development e DEV_AUTH_BYPASS=1", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("DEV_AUTH_BYPASS", "1");
    const r = await middleware(pedido("/crafting/calculadora"));
    expect(r.headers.get("location")).toBeNull();
    // Observável de fora, para o estado não ser silencioso.
    expect(r.headers.get("x-dev-auth-bypass")).toBe("1");
  });

  it("NÃO liga só com NODE_ENV=development", async () => {
    vi.stubEnv("NODE_ENV", "development");
    const r = await middleware(pedido("/crafting/calculadora"));
    expect(r.headers.get("location")).toContain("/login");
  });

  it("NÃO liga só com DEV_AUTH_BYPASS=1", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("DEV_AUTH_BYPASS", "1");
    const r = await middleware(pedido("/crafting/calculadora"));
    expect(r.headers.get("location")).toContain("/login");
  });

  it("o valor precisa ser exatamente \"1\"", async () => {
    vi.stubEnv("NODE_ENV", "development");
    for (const valor of ["true", "yes", "0", "sim", " 1"]) {
      vi.stubEnv("DEV_AUTH_BYPASS", valor);
      const r = await middleware(pedido("/crafting/calculadora"));
      expect(r.headers.get("location"), `valor ${JSON.stringify(valor)}`).toContain("/login");
    }
  });

  it("libera a passagem e NÃO forja identidade", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("DEV_AUTH_BYPASS", "1");
    const r = await middleware(pedido("/crafting/calculadora"));
    // Nenhum cookie de sessão é plantado: a sessão segue nula, que é o mesmo
    // estado do modo aberto. O desvio não cria caminho de código novo.
    expect(r.headers.get("set-cookie")).toBeNull();
  });
});
