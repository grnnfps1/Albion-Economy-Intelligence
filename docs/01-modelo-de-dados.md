# 01 — Modelo de dados

> Documento da FASE 0, atualizado no fim da FASE 2 com o que a implementação
> obrigou a mudar. As migrations `0001` e `0002` implementam a seção "Núcleo".

Convenções globais:

- Toda coluna de tempo é `TIMESTAMPTZ`, sempre gravada em UTC.
- Preços em silver são `BIGINT` (inteiro). Nunca float — silver é unidade inteira e
  float introduz erro de arredondamento em cálculo de margem.
- Percentuais e multiplicadores são `NUMERIC(9,6)`.
- Toda tabela de mercado carrega `server_id`. Não existe consulta cross-server.
- `created_at` / `updated_at` em toda tabela mutável.

---

## Núcleo (FASE 2)

### `servers`
| coluna | tipo | nota |
|---|---|---|
| id | smallint PK | |
| code | text UNIQUE | `west`, `east`, `europe` |
| display_name | text | Americas, Asia, Europe |
| aodp_base_url | text | `https://west.albion-online-data.com` |
| active | boolean | |

### `locations`
Cidades **e** Black Market na mesma tabela, separados por `kind`. Black Market não é
cidade (item 31), mas é um local de mercado — modelar fora da tabela criaria dois
caminhos de código para a mesma consulta.

| coluna | tipo | nota |
|---|---|---|
| id | smallint PK | |
| aodp_name | text UNIQUE | string exata do AODP: `Fort Sterling`, `Black Market` |
| slug | text UNIQUE | `fort-sterling`, `black-market` |
| display_name | text | |
| kind | enum | `royal_city` \| `black_market` \| `portal_city` \| `rest_zone` |
| supports_buy_orders | boolean | BM tem semântica diferente — ver doc 02 |
| active | boolean | |

Seed: Caerleon, Bridgewatch, Lymhurst, Fort Sterling, Martlock, Thetford, Brecilien,
Black Market.

### `item_categories`
| coluna | tipo | nota |
|---|---|---|
| id | smallint PK | |
| code | text UNIQUE | vem de `@shopcategory` do dump |
| parent_id | smallint FK NULL | auto-referência, para hierarquia futura |
| display_name | text | |

Os 16 códigos existentes não foram escolhidos: são os valores de `@shopcategory`
que apareceram no dump (`crafting`, `weapons`, `armors`, `bags`, `gathering`, …).
A subcategoria fica em `items.subcategory_code` como texto, porque `@shopsubcategory1`
não é um espaço de nomes independente do pai.

### `items`
| coluna | tipo | nota |
|---|---|---|
| id | integer PK | |
| unique_name | text UNIQUE | **chave lógica**: `T5_LEATHER`, `T4_BAG@1` |
| base_name | text | `T5_LEATHER` sem encantamento |
| tier | smallint | 1–8 |
| enchantment | smallint | 0–4 |
| category_id | smallint FK | |
| display_name_en | text NULL | de `ao-bin-dumps` |
| display_name_pt | text NULL | |
| weight | numeric(10,4) NULL | para custo de transporte |
| shop_category | text NULL | |
| active | boolean | |

`unique_name` é a única chave usada em joins e requisições (item 10). Nome visual é
apresentação e pode mudar por patch ou locale.

**Parsing, com o que a implementação revelou.** O identificador tem três formatos
reais, todos presentes em `formatted/items.txt`:

```
T4_PLANKS              base
T4_BAG@1               equipamento encantado
T4_PLANKS_LEVEL1@1     recurso refinado encantado
```

O sufixo `@N` é a autoridade sobre o encantamento. Já o `_LEVELN` é ambíguo: quase
sempre marca a variante encantada (`T4_PLANKS_LEVEL1` é o `T4_PLANKS` encantado),
mas em alguns itens faz parte do nome de verdade — `T1_FISHSAUCE_LEVEL1`,
`_LEVEL2` e `_LEVEL3` são três itens distintos, não encantamentos. Não dá para
decidir olhando só a string: `resolve_base_name()` consulta o que existe no dump
antes de agrupar.

O parser foi validado contra os 12.237 identificadores reais: zero falhas.

**Duas fontes, papéis diferentes.** `formatted/items.json` é a lista canônica de
identificadores — inclui as variantes encantadas e é exatamente o vocabulário que
o AODP usa. O `items.json` da raiz traz os metadados (tier, peso, categoria,
qualidade máxima e **receitas**), mas só de itens base: as variantes encantadas
ficam aninhadas em `enchantments`. 266 identificadores não têm metadado em lugar
nenhum e entram com NULL.

**`is_tracked`** marca o subconjunto que os collectors varrem. Varrer 12 mil
identificadores a 1 req/s não fecha a conta (risco R5). O padrão são as
subcategorias `resources`, `refinedresources`, `cityresources` e `tokens` — 312
itens. Detalhe que a intuição erra: recurso bruto é `resources`, não
`rawresources`.

### `market_prices` — snapshot atual
Uma linha por `(server, location, item, quality)`, atualizada por UPSERT.

| coluna | tipo |
|---|---|
| server_id | smallint FK |
| location_id | smallint FK |
| item_id | integer FK |
| quality | smallint (1–5) |
| sell_price_min / sell_price_max | bigint NULL |
| sell_price_min_date / sell_price_max_date | timestamptz NULL |
| buy_price_min / buy_price_max | bigint NULL |
| buy_price_min_date / buy_price_max_date | timestamptz NULL |
| observed_at | timestamptz — quando o collector buscou |
| source_id | smallint FK `data_sources` |

`PRIMARY KEY (server_id, location_id, item_id, quality)`
Índices: `(server_id, item_id)`, `(server_id, location_id, observed_at DESC)`.

**Sentinelas:** o AODP devolve `0` + `0001-01-01T00:00:00` quando não há ordem. Isso
vira `NULL`, nunca `0` (requisito 52). Preço zero e ausência de preço são coisas
diferentes e confundi-las gera "arbitragem" de lucro infinito.

**Idade do dado** não é coluna — é derivada (`now() - *_date`) na camada de
apresentação, com o status (`FRESH`/`STALE`/`OLD`) vindo de configuração.

### `market_price_observations` — log append-only
Mesmas colunas de `market_prices` + `id bigserial`. Serve para (a) tendência de curto
prazo que o endpoint de history não cobre e (b) auditoria. Particionada por mês, com
retenção configurável. **Opcional na Fase 2**, obrigatória antes da Fase 6.

### `market_history`
| coluna | tipo |
|---|---|
| server_id / location_id / item_id / quality | FK |
| timescale | smallint — 1, 6 ou 24 (horas) |
| bucket_ts | timestamptz |
| item_count | integer |
| avg_price | bigint |
| is_outlier | boolean — marcado pela normalização |
| source_id | smallint FK |

`PRIMARY KEY (server_id, location_id, item_id, quality, timescale, bucket_ts)`

O history do AODP é **só de sell orders** e é média, não mediana — por isso
`is_outlier` (ver doc 02, seção de outliers).

### `gold_prices`
| coluna | tipo |
|---|---|
| server_id | smallint FK |
| ts | timestamptz |
| price | integer — silver por gold |

`PRIMARY KEY (server_id, ts)`

### `data_sources`
| coluna | tipo | nota |
|---|---|---|
| id | smallint PK | |
| code | text UNIQUE | `aodp`, `ao-bin-dumps`, `manual`, `mock` |
| base_url | text NULL | |
| is_community_sourced | boolean | `true` para AODP |
| notes | text | |

Toda linha de mercado aponta para uma fonte. É isso que permite responder "de onde veio
esse número" (requisito 17) e marcar visualmente dado mock.

### `collector_runs`
`id, collector, server_id, started_at, finished_at, status, http_requests,
rows_upserted, rows_rejected, rate_limited_count, error_message`.

Base da observabilidade (requisito 40) e do health check de frescor.

### `raw_responses`
`id, source_id, endpoint, request_url, server_id, fetched_at, http_status,
payload JSONB, payload_sha256`.

Retenção curta (7–14 dias, configurável). Sem isso é impossível auditar uma
normalização errada depois do fato.

---

## Configuração (FASE 2, consumida a partir da FASE 6)

### `config_parameters`
`key TEXT PK, value JSONB, scope TEXT, description TEXT, updated_at`.

Taxas **nunca** ficam em código (requisito 26). Chaves previstas:

```
market.sell_order_setup_fee_pct
market.sales_tax_pct.premium
market.sales_tax_pct.standard
crafting.station_fee_formula
crafting.return_rate.base
crafting.return_rate.focus
freshness.fresh_seconds
freshness.stale_seconds
score.weights.{profit,margin,roi,freshness,liquidity,trend,distance,risk}
```

Os valores reais de taxa/return rate **não estão preenchidos neste documento** porque
não foram verificados contra o jogo. Entram na Fase 7/8 com fonte citada. Até lá o
sistema retorna `UNKNOWN`, não um chute.

---

## Inteligência (FASES 6–9)

### `recipes` / `recipe_materials`
`recipes(id, output_item_id, output_quantity, station_type, focus_cost, active)`
`recipe_materials(recipe_id, item_id, quantity, is_returnable)`

`is_returnable` importa: o return rate se aplica só a materiais elegíveis.

Boa notícia descoberta na FASE 2: **a fonte já está em mãos.** O `items.json` da
raiz do dump traz `craftingrequirements` com `@craftingfocus`, `@silver`,
`@amountcrafted` e a lista de `craftresource`. Exemplo real de `T4_PLANKS`: focus
54, 2× `T4_WOOD` + 1× `T3_PLANKS`. A FASE 7 não precisa de fonte nova, só de um
segundo passe sobre o arquivo que o importador já baixa.

### `transport_routes`
`id, origin_location_id, destination_location_id, distance_label, base_cost_per_weight,
estimated_minutes, risk_level, is_manual`.

Fase 6 começa com custo manual (item 25).

### `opportunities`
`id, kind, server_id, item_id, quality, origin_location_id, destination_location_id,
cost, revenue, profit, margin, roi, focus_cost, profit_per_focus, liquidity_score,
liquidity_status, score, confidence, computed_at, expires_at, inputs JSONB`.

`inputs` guarda os preços e taxas usados no cálculo. Sem isso, uma oportunidade antiga
vira um número sem explicação. `liquidity_status` ∈ `KNOWN | UNKNOWN` — nunca inventar
liquidez (requisito 21).

---

## Privado / comercial (FASES futuras)

Separação explícita (itens 74–75): estas tabelas carregam `user_id`; as públicas acima
nunca são duplicadas por usuário.

```
users(id, email, discord_id, status, created_at)
plans(id, code, display_name, active)
entitlements(id, code)                     -- 'history.90d', 'crafting.focus', ...
plan_entitlements(plan_id, entitlement_id, limit_value JSONB NULL)
subscriptions(id, user_id, plan_id, status, started_at, expires_at, gateway_ref)
licenses(id, code, user_id, plan_id, status, device_limit, request_limit,
         activated_at, expires_at, last_used_at, use_count)
api_keys(id, user_id, plan_id, key_hash, prefix, status, rate_limit,
         request_count, expires_at, last_used_at)
watchlists(id, user_id, server_id, item_id, location_id NULL)
alerts(id, user_id, kind, condition JSONB, channel, status, last_fired_at)
portfolios / transactions(id, user_id, kind, item_id, quantity, unit_price, fees, ts)
audit_logs(id, actor_user_id, action, target_type, target_id, ip, result, ts)
```

Pontos que precisam estar certos desde já, porque são caros de consertar depois:

- **`api_keys.key_hash`** — nunca a chave em claro (item 63). Hash forte + `prefix`
  visível (`AEB-7F3A…`) para o usuário identificar a chave sem revelá-la.
- **Entitlements são dados, não `if`.** A checagem é
  `require("history.90d")`, jamais `if user.plan == "premium"` (item 62).
- **Ativação de plano só via webhook do gateway** (item 67). O frontend nunca ativa nada.
