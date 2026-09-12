/**
 * Acesso ao backend — SOMENTE do lado do servidor.
 *
 * O browser nunca fala com o FastAPI. Ele chama os Route Handlers do Next, que
 * chamam este módulo. Assim a URL interna do backend e qualquer credencial de
 * serviço ficam fora do bundle do cliente (docs/00-arquitetura.md §4).
 */
import "server-only";

const BASE_URL = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

export type ComponentHealth = {
  status: string;
  latency_ms: number | null;
  detail: string | null;
};

export type AodpServerHealth = {
  server: string;
  status: string;
  status_code: number | null;
  latency_ms: number | null;
  detail: string | null;
};

export type CatalogMeta = {
  servers: { code: string; display_name: string }[];
  locations: { slug: string; aodp_name: string; display_name: string; kind: string }[];
  categories: { code: string; display_name: string }[];
  catalog: { total: number; tracked: number };
  data_source: string;
  data_source_note: string;
};

export type PlatformStatus = {
  reachable: boolean;
  app: string | null;
  environment: string | null;
  version: string | null;
  mockData: boolean;
  database: ComponentHealth | null;
  cache: ComponentHealth | null;
  aodp: AodpServerHealth[];
  error: string | null;
};

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal: AbortSignal.timeout(10_000),
  });
  // 503 é resposta legítima do health check degradado: tem corpo útil.
  if (!response.ok && response.status !== 503) {
    throw new Error(`${path} respondeu ${response.status}`);
  }
  return (await response.json()) as T;
}

/**
 * Catálogo e listas de filtro.
 *
 * Vem da API justamente para que cidade, servidor e categoria não fiquem
 * escritas no código do frontend: adicionar uma localidade é seed de banco,
 * não deploy de frontend.
 */
export async function fetchCatalogMeta(): Promise<CatalogMeta | null> {
  try {
    return await getJson<CatalogMeta>("/api/v1/meta");
  } catch {
    return null;
  }
}

export async function fetchPlatformStatus(): Promise<PlatformStatus> {
  try {
    const [live, infra, aodp] = await Promise.all([
      getJson<{ app: string; environment: string; version: string; mock_data: boolean }>("/health"),
      getJson<{ database: ComponentHealth; cache: ComponentHealth }>("/health/database"),
      getJson<{ servers: AodpServerHealth[] }>("/health/aodp"),
    ]);

    return {
      reachable: true,
      app: live.app,
      environment: live.environment,
      version: live.version,
      mockData: live.mock_data,
      database: infra.database,
      cache: infra.cache,
      aodp: aodp.servers,
      error: null,
    };
  } catch (error) {
    return {
      reachable: false,
      app: null,
      environment: null,
      version: null,
      mockData: false,
      database: null,
      cache: null,
      aodp: [],
      error: error instanceof Error ? error.message : "falha desconhecida",
    };
  }
}
