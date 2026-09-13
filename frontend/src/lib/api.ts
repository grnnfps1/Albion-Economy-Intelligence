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

export type Freshness = "ATUALIZADO" | "DESATUALIZADO" | "ANTIGO" | "DESCONHECIDO";

export type PriceField = {
  value: number | null;
  age_seconds: number | null;
  freshness: Freshness;
};

export type Liquidity = {
  status: "KNOWN" | "UNKNOWN";
  units_per_day: number | null;
  days_with_data: number;
  period_days: number;
};

export type MarketPrice = {
  item: string;
  item_name: string | null;
  icon_url: string | null;
  tier: number | null;
  enchantment: number;
  location: string;
  location_kind: string;
  quality: number;
  sell_min: PriceField;
  sell_max: PriceField;
  buy_min: PriceField;
  buy_max: PriceField;
  observed_age_seconds: number;
  observed_freshness: Freshness;
  liquidity: Liquidity;
  median_30d: number | null;
  vs_median_pct: number | null;
};

export type MarketPricePage = {
  server: string;
  total: number;
  limit: number;
  offset: number;
  sort_by: string;
  descending: boolean;
  generated_at: string;
  data_source_note: string;
  prices: MarketPrice[];
};

export type MarketQuery = {
  server?: string;
  locations?: string;
  search?: string;
  tier?: string;
  enchantment?: string;
  qualities?: string;
  sort_by?: string;
  descending?: string;
  limit?: string;
  offset?: string;
};

export async function fetchMarketPrices(query: MarketQuery): Promise<MarketPricePage | null> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, value);
  }
  try {
    return await getJson<MarketPricePage>(`/api/v1/market/prices?${params.toString()}`);
  } catch {
    return null;
  }
}

export type Trend = "ALTA" | "ESTAVEL" | "BAIXA" | "DESCONHECIDA";

export type HistoryPoint = {
  timestamp: string;
  avg_price: number;
  item_count: number;
  is_outlier: boolean;
};

export type HistorySeries = {
  location: string;
  location_slug: string;
  quality: number;
  points: HistoryPoint[];
  minimum: number | null;
  maximum: number | null;
  average: number | null;
  median: number | null;
  outlier_count: number;
  change_pct: number | null;
  trend: Trend;
};

export type HistoryResponse = {
  server: string;
  item: string;
  item_name: string | null;
  timescale: number;
  period_days: number;
  total_points: number;
  series: HistorySeries[];
  data_source_note: string;
};

export type GoldResponse = {
  server: string;
  points: { timestamp: string; price: number }[];
  current: number | null;
  minimum: number | null;
  maximum: number | null;
  median: number | null;
  change_pct: number | null;
  trend: Trend;
};

export async function fetchHistory(
  query: Record<string, string | undefined>,
): Promise<HistoryResponse | null> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value) params.set(key, value);
  }
  try {
    return await getJson<HistoryResponse>(`/api/v1/market/history?${params.toString()}`);
  } catch {
    return null;
  }
}

export async function fetchGold(server: string, days: string): Promise<GoldResponse | null> {
  try {
    return await getJson<GoldResponse>(`/api/v1/gold?server=${server}&days=${days}`);
  } catch {
    return null;
  }
}

export type Economics = {
  known: boolean;
  reason: string | null;
  quantity: number;
  unit_cost: number | null;
  investment: number | null;
  gross_revenue: number | null;
  fees: number | null;
  transport_cost: number | null;
  net_profit: number | null;
  margin_pct: number | null;
  roi_pct: number | null;
};

export type Opportunity = {
  item: string; item_name: string | null; icon_url: string | null;
  tier: number | null; enchantment: number; quality: number;
  strategy: string;
  origin: string; origin_slug: string;
  destination: string; destination_slug: string;
  buy_price: number; sell_price: number; spread_pct: number;
  worst_age_seconds: number;
  liquidity_units_per_day: number | null;
  economics: Economics;
  score: { value: number | null; band: string; confidence: number;
           components: Record<string, number>; missing: string[] };
};

export type ArbitrageResponse = {
  server: string; strategy: string; quantity: number; total: number;
  fees: { setup_fee_pct: number | null; sales_tax_pct: number | null;
          premium: boolean | null; source: string; complete: boolean; missing: string[] };
  generated_at: string; data_source_note: string;
  opportunities: Opportunity[];
};

export async function fetchArbitrage(
  query: Record<string, string | undefined>,
): Promise<ArbitrageResponse | null> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) if (value) params.set(key, value);
  try {
    return await getJson<ArbitrageResponse>(`/api/v1/arbitrage?${params.toString()}`);
  } catch {
    return null;
  }
}

export type CraftMaterial = {
  item: string; item_name: string | null; icon_url: string | null;
  quantity: number; unit_price: number | null; total_price: number | null;
  is_returnable: boolean; location: string | null; age_seconds: number | null;
};

export type CraftOpportunity = {
  item: string; item_name: string | null; icon_url: string | null;
  tier: number | null; enchantment: number; recipe_variant: number;
  station_category: string | null;
  buy_location: string; sell_location: string;
  sell_price: number | null; sell_age_seconds: number | null;
  liquidity_units_per_day: number | null;
  materials: CraftMaterial[];
  economics: {
    known: boolean; reason: string | null;
    output_quantity: number; focus_cost: number;
    material_cost_gross: number | null; material_cost_net: number | null;
    returned_value: number | null; station_fee: number | null;
    sale_revenue_net: number | null; market_fees: number | null;
    profit: number | null; margin_pct: number | null; roi_pct: number | null;
    profit_per_focus: number | null;
  };
};

export type CraftingResponse = {
  server: string; buy_location: string; sell_location: string;
  crafts: number; sort_by: string; total: number;
  params: {
    return_rate: number | null; station_fee: number | null;
    fees: { setup_fee_pct: number | null; sales_tax_pct: number | null;
            premium: boolean | null; source: string; complete: boolean; missing: string[] };
    complete: boolean; missing: string[];
  };
  generated_at: string; data_source_note: string;
  opportunities: CraftOpportunity[];
};

export async function fetchCrafting(
  query: Record<string, string | undefined>,
): Promise<CraftingResponse | null> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) if (value) params.set(key, value);
  try {
    return await getJson<CraftingResponse>(`/api/v1/crafting/opportunities?${params.toString()}`);
  } catch {
    return null;
  }
}

export type ChainStep = {
  item: string; item_name: string | null; icon_url: string | null;
  sourcing: string; unit_cost: number | null;
  market_price: number | null; craft_cost: number | null; depth: number;
};

export type RefiningOpportunity = {
  item: string; item_name: string | null; icon_url: string | null;
  tier: number | null; enchantment: number; family: string | null;
  station_category: string | null;
  sell_price: number | null; sell_age_seconds: number | null;
  liquidity_units_per_day: number | null;
  sourcing: string; unit_cost: number | null; focus_per_unit: number;
  chain: ChainStep[];
  cost_from_market: number | null; cost_from_crafting: number | null;
  known: boolean; reason: string | null;
  profit: number | null; margin_pct: number | null; profit_per_focus: number | null;
};

export type RefiningResponse = {
  server: string; buy_location: string; sell_location: string; sourcing: string;
  total: number; families: string[];
  params: CraftingResponse["params"];
  generated_at: string; data_source_note: string;
  opportunities: RefiningOpportunity[];
};

export async function fetchRefining(
  query: Record<string, string | undefined>,
): Promise<RefiningResponse | null> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) if (value) params.set(key, value);
  try {
    return await getJson<RefiningResponse>(`/api/v1/refining/opportunities?${params.toString()}`);
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
