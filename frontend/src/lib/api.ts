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

/**
 * Quem está pedindo, para o backend.
 *
 * O FastAPI não valida sessão — quem valida é o `middleware.ts`, e o backend
 * não é exposto ao browser. O cabeçalho só pode ter sido posto aqui, depois de
 * o cookie assinado ser verificado.
 *
 * `null` é o modo de desenvolvimento local, sem login: o backend responde como
 * sempre respondeu, sem sobrescritas.
 */
async function userHeader(): Promise<Record<string, string>> {
  const { getSession } = await import("@/lib/auth");
  const session = await getSession();
  return session ? { "X-User-Id": session.id } : {};
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json", ...(await userHeader()) },
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
  /** O valor exibido veio do usuário, não da coleta. */
  is_manual: boolean;
  /** O que a coleta dizia, quando o manual venceu. Ver os dois lado a lado é
   *  o que permite perceber um zero a mais. */
  collected_value: number | null;
  /** Existe preço manual aqui, mas expirou. Dizer é melhor que ignorar. */
  manual_expired: boolean;
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

export type ManualPrice = {
  server: string;
  location: string;
  location_name: string;
  item: string;
  item_name: string | null;
  icon_url: string | null;
  quality: number;
  price: number;
  kind: "COMPRA" | "VENDA";
  informed_at: string;
  age_seconds: number;
  is_stale: boolean;
};

export type ManualPriceList = {
  server: string;
  total: number;
  max_age_seconds: number;
  prices: ManualPrice[];
};

export async function fetchManualPrices(server: string): Promise<ManualPriceList | null> {
  try {
    return await getJson<ManualPriceList>(`/api/v1/manual-prices?server=${server}`);
  } catch {
    // 401 sem sessão é resposta legítima: preço manual é por usuário.
    return null;
  }
}

/** Grava ou atualiza. Reinformar renova a idade — é o ponto. */
export async function saveManualPrice(body: {
  server: string; location: string; item: string;
  quality: number; price: number; kind: "COMPRA" | "VENDA";
}): Promise<ManualPrice | null> {
  const response = await fetch(`${BASE_URL}/api/v1/manual-prices`, {
    method: "PUT",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(await userHeader()),
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(10_000),
  });
  return response.ok ? ((await response.json()) as ManualPrice) : null;
}

/** Apagar é como se diz "volte a usar o preço coletado". */
export async function deleteManualPrice(query: {
  server: string; location: string; item: string; quality: number; kind: string;
}): Promise<boolean> {
  const params = new URLSearchParams(
    Object.entries(query).map(([k, v]) => [k, String(v)]),
  );
  const response = await fetch(`${BASE_URL}/api/v1/manual-prices?${params}`, {
    method: "DELETE",
    cache: "no-store",
    headers: { Accept: "application/json", ...(await userHeader()) },
    signal: AbortSignal.timeout(10_000),
  });
  return response.ok;
}

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
  risk: RouteRisk;
  economics: Economics;
  score: { value: number | null; band: string; confidence: number;
           components: Record<string, number>; missing: string[] };
};

export type ArbitrageResponse = {
  server: string; strategy: string; quantity: number; total: number;
  fees: { setup_fee_pct: number | null; sales_tax_pct: number | null;
          premium: boolean | null; source: string; complete: boolean; missing: string[] };
  risk: RiskUsed;
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

/** Retorno de material em uso, e onde ele seria maior. */
export type MaterialReturn = {
  rate: number | null; source: string;
  has_city_bonus: boolean; use_focus: boolean;
  daily_bonus: number; assumes_no_daily_bonus: boolean;
  bonus_total: number | null; is_island: boolean;
  components: { key: string; label: string; value: number; applies: boolean }[];
  matrix_rate: number | null;
  best_city: string | null; best_city_name: string | null;
  rate_at_best_city: number | null; delta: number | null;
  is_best_city: boolean; mapping_known: boolean;
};

/** Risco de rota: os dois números lado a lado, o bruto e o ajustado. */
export type RouteRisk = {
  zone: string; zone_label: string; crosses_open_world: boolean;
  loss_probability: number;
  gross_profit: number | null; investment: number | null;
  expected_profit: number | null; expected_loss: number | null;
  survives_risk: boolean;
};

export type RiskUsed = {
  loss_pct_blue: number; loss_pct_red_black: number;
  source: string; modelled: boolean;
};

export type CraftMaterial = {
  item: string; item_name: string | null; icon_url: string | null;
  quantity: number; unit_price: number | null; total_price: number | null;
  is_returnable: boolean; location: string | null; location_slug: string | null;
  age_seconds: number | null;
  is_alternate_city: boolean; base_unit_price: number | null;
  savings_vs_base: number | null;
};

/** O roteiro de compra: por quantas cidades ele passa e quanto isso rende. */
export type MaterialSourcing = {
  mode: string; cities_involved: number; cities: string[];
  cost_single_city: number | null; cost_cheapest: number | null;
  savings: number | null; savings_pct: number | null;
  profit_single_city: number | null; profit_cheapest: number | null;
};

export type CraftOpportunity = {
  item: string; item_name: string | null; icon_url: string | null;
  tier: number | null; enchantment: number; recipe_variant: number;
  station_category: string | null;
  buy_location: string; sell_location: string;
  sell_price: number | null; sell_age_seconds: number | null;
  liquidity_units_per_day: number | null;
  materials: CraftMaterial[];
  material_sourcing: MaterialSourcing;
  risk: RouteRisk;
  material_return: MaterialReturn;
  economics: {
    known: boolean; reason: string | null;
    output_quantity: number; focus_cost: number;
    material_cost_gross: number | null; material_cost_net: number | null;
    returned_value: number | null; station_fee: number | null;
    item_value: number | null; nutrition: number | null;
    /** Focus antes da especialização — o `@craftingfocus` do dump. */
    base_focus_cost: number | null;
    focus_multiplier: number | null;
    profit_per_day: number | null;
    units_per_day: number | null;
    daily_limiter: string;
    daily_reason: string | null;
    sale_revenue_net: number | null; market_fees: number | null;
    profit: number | null; margin_pct: number | null; roi_pct: number | null;
    profit_per_focus: number | null;
  };
};

export type CraftingResponse = {
  server: string; buy_location: string; sell_location: string;
  crafts: number; sort_by: string; sourcing_mode: string; total: number;
  params: {
    return_rate: number | null; station_fee_per_100_nutrition: number | null;
    nutrition_per_item_value: number | null;
    specialization?: {
      informed: boolean; assumes_zero_spec: boolean;
      levels: Record<string, number>;
      item_levels: Record<string, number>;
      families: string[];
    };
    use_focus: boolean; daily_production_bonus: number; return_rate_source: string;
    fees: { setup_fee_pct: number | null; sales_tax_pct: number | null;
            premium: boolean | null; source: string; complete: boolean; missing: string[] };
    complete: boolean; missing: string[];
  };
  risk: RiskUsed;
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
  location: string | null; location_slug: string | null;
  is_alternate_city: boolean; base_unit_price: number | null;
  savings_vs_base: number | null;
  /** Qual variante da receita o motor usou, e qual descartou. */
  variant_label: string | null;
  alternative_cost: number | null; alternative_label: string | null;
};

export type RefiningOpportunity = {
  item: string; item_name: string | null; icon_url: string | null;
  tier: number | null; enchantment: number; family: string | null;
  station_category: string | null;
  sell_price: number | null; sell_age_seconds: number | null;
  liquidity_units_per_day: number | null;
  sourcing: string; unit_cost: number | null; focus_per_unit: number;
  chain: ChainStep[];
  material_sourcing: MaterialSourcing;
  material_return: MaterialReturn;
  cost_from_market: number | null; cost_from_crafting: number | null;
  known: boolean; reason: string | null;
  profit: number | null; margin_pct: number | null; profit_per_focus: number | null;
  profit_per_day: number | null; units_per_day: number | null;
  daily_limiter: string; daily_reason: string | null;
};

export type RefiningResponse = {
  server: string; buy_location: string; sell_location: string; sourcing: string;
  sourcing_mode: string; total: number; families: string[];
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

export type FocusPlan = {
  item: string; item_name: string | null; icon_url: string | null;
  tier: number | null; enchantment: number; route: string;
  profit_per_unit: number; focus_per_unit: number; profit_per_focus: number | null;
  units_by_focus: number | null; units_by_liquidity: number | null;
  units: number | null; focus_used: number | null;
  realizable_profit: number | null; limiter: string;
  days_to_sell: number | null; liquidity_units_per_day: number | null;
};

export type FocusResponse = {
  server: string; buy_location: string; sell_location: string;
  focus_budget: number | null; horizon_days: number; sort_by: string; total: number;
  params: CraftingResponse["params"];
  generated_at: string; data_source_note: string;
  plans: FocusPlan[];
};

export async function fetchFocus(
  query: Record<string, string | undefined>,
): Promise<FocusResponse | null> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) if (value) params.set(key, value);
  try {
    return await getJson<FocusResponse>(`/api/v1/focus/ranking?${params.toString()}`);
  } catch {
    return null;
  }
}

export type DashboardCard = {
  kind: string; available: boolean; reason: string | null;
  item: string | null; item_name: string | null; icon_url: string | null;
  tier: number | null;
  headline: number | null; headline_label: string | null; detail: string | null;
  age_seconds: number | null; freshness: Freshness;
  score: number | null; confidence: number | null;
  liquidity_units_per_day: number | null; href: string;
};

export type DashboardResponse = {
  server: string; generated_at: string;
  pipeline: {
    prices_tracked: number; last_collection_age_seconds: number | null;
    freshness: Freshness; last_run_status: string | null;
    stale_price_ratio: number | null;
  };
  params: CraftingResponse["params"];
  cards: DashboardCard[];
  top_opportunities: DashboardCard[];
  data_source_note: string;
};

export async function fetchDashboard(
  query: Record<string, string | undefined>,
): Promise<DashboardResponse | null> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) if (value) params.set(key, value);
  try {
    return await getJson<DashboardResponse>(`/api/v1/dashboard?${params.toString()}`);
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

export type FarmInput = {
  item: string; item_name: string | null; icon_url: string | null;
  role: string; quantity: number; unit_price: number | null; total_price: number | null;
  location: string | null; location_slug: string | null; age_seconds: number | null;
  is_alternate_city: boolean; savings_vs_base: number | null;
};

export type FarmOutput = {
  item: string; item_name: string | null; icon_url: string | null;
  role: string; amount_min: number; amount_max: number; chance: number;
  expected_amount: number; unit_price: number | null; primary: boolean;
};

export type FarmPlan = {
  item: string; item_name: string | null; icon_url: string | null;
  tier: number | null; station: string; station_label: string; kind: string;
  buy_location: string; sell_location: string;
  focus_cycles: number | null; liquidity_units_per_day: number | null;
  npc_silver_cost: number | null;
  inputs: FarmInput[]; outputs: FarmOutput[];
  material_sourcing: MaterialSourcing;
  economics: {
    known: boolean; reason: string | null; kind: string;
    cycle_seconds: number; cycle_days: number; focus_cost: number;
    input_cost: number | null; gross_revenue: number | null;
    sale_revenue_net: number | null; market_fees: number | null;
    profit_per_cycle: number | null; profit_per_day: number | null;
    profit_per_focus: number | null; focus_per_day: number | null;
    margin_pct: number | null; roi_pct: number | null;
    outputs_without_price: string[];
  };
};

export type FarmingResponse = {
  server: string; buy_location: string; sell_location: string;
  sort_by: string; sourcing_mode: string; total: number;
  params: {
    fees: { setup_fee_pct: number | null; sales_tax_pct: number | null;
            premium: boolean | null; source: string; complete: boolean; missing: string[] };
    complete: boolean; missing: string[]; assumptions: string[];
  };
  generated_at: string; data_source_note: string;
  stations: string[]; plans: FarmPlan[];
};

export async function fetchFarming(
  query: Record<string, string | undefined>,
): Promise<FarmingResponse | null> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) if (value) params.set(key, value);
  try {
    return await getJson<FarmingResponse>(`/api/v1/farming/plans?${params.toString()}`);
  } catch {
    return null;
  }
}

// --------------------------------------------------------------------------- //
// Calculador de crafting (fase 19)
// --------------------------------------------------------------------------- //

/** Um local e o retorno que ele daria para a família em tela. */
export type ReturnOption = {
  slug: string;
  name: string;
  rate: number | null;
  has_city_bonus: boolean;
  is_island: boolean;
  is_current: boolean;
  is_best: boolean;
};

/** Uma cidade com cotação de um material. Vai no balão, não na coluna. */
export type CityQuote = {
  location_slug: string;
  location_name: string;
  unit_price: number;
  age_seconds: number | null;
  is_fresh: boolean;
  is_manual: boolean;
  is_chosen: boolean;
};

export type PriceRange = {
  cities: CityQuote[];
  min_price: number | null;
  max_price: number | null;
  spread: number | null;
  spread_pct: number | null;
  fresh_city_count: number;
  /** Falso significa **falta de alternativa**, não espalhamento zero. */
  comparable: boolean;
};

export type CalcMaterial = {
  item: string;
  item_name: string | null;
  icon_url: string | null;
  quantity: number;
  is_returnable: boolean;
  /** "bruto" | "refinado" | "token" | "outro" — define a coluna, não a ordem do dump. */
  role: string;
  unit_price: number | null;
  price_is_manual: boolean;
  collected_price: number | null;
  age_seconds: number | null;
  location: string | null;
  is_alternate_city: boolean;
  buy_units: number;
  gross_units: number;
  saved_by_return: number;
  price_range: PriceRange | null;
};

export type CalcRow = {
  item: string;
  item_name: string | null;
  icon_url: string | null;
  tier: number | null;
  enchantment: number;
  tier_label: string;
  sell_price: number | null;
  sell_price_is_manual: boolean;
  sell_collected_price: number | null;
  sell_age_seconds: number | null;
  liquidity_units_per_day: number | null;
  materials: CalcMaterial[];
  variant_label: string | null;
  alternative_label: string | null;
  alternative_cost: number | null;
  material_cost: number | null;
  material_cost_gross: number | null;
  returned_value: number | null;
  station_fee: number | null;
  sale_fee: number | null;
  production_cost: number | null;
  gross_revenue: number | null;
  profit: number | null;
  margin_pct: number | null;
  margin_on_cost_pct: number | null;
  focus_cost: number;
  profit_per_focus: number | null;
  total_profit: number | null;
  total_investment: number | null;
  days_to_sell: number | null;
  known: boolean;
  reason: string | null;
  /** "parametro" | "cotacao" | "ambos" — quem consegue destravar a linha. */
  blocker: string | null;
  blocked_data: string[];
};

export type CalculatorResponse = {
  server: string;
  family: string;
  families: string[];
  buy_location: string;
  sell_location: string;
  rows: CalcRow[];
  material_return: MaterialReturn;
  return_options: ReturnOption[];
  params: {
    quantity: number;
    sourcing: string;
    strategy: string;
    station_fee_per_100_nutrition: number | null;
    nutrition_per_item_value: number | null;
    focus_per_day: number | null;
    fees: { setup_fee_pct: number | null; sales_tax_pct: number | null; premium: boolean | null };
    specialization?: { informed: boolean; assumes_zero_spec: boolean };
    complete: boolean;
    missing: string[];
  };
  return_note: string;
  generated_at: string;
  data_source_note: string;
};

export async function fetchCalculator(
  query: Record<string, string>,
): Promise<CalculatorResponse | null> {
  const params = new URLSearchParams(query);
  try {
    return await getJson<CalculatorResponse>(`/api/v1/crafting/calculator?${params}`);
  } catch {
    return null;
  }
}
