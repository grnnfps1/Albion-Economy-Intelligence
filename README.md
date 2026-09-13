# Albion Economy Intelligence

Motor de inteligência econômica para Albion Online. Transforma os dados de mercado do
Albion Online Data Project em oportunidades acionáveis: arbitragem, crafting,
refinamento e prata por Focus.

**Estado: FASE 8 concluída — refino.** A plataforma coleta preços e histórico do
AODP, marca outliers, e entrega `/market`, `/market/history`, `/gold`,
`/arbitrage`, `/crafting` e `/refining`. Imposto, retorno de material e taxa de estação são
**entrada do usuário** — nenhum é constante, e uma calculadora que os fixa está
errada para quase todo mundo. Sem eles, a resposta é `UNKNOWN` com o motivo, e
nunca um número calculado com taxa zero.

---

## Stack

| Camada | Tecnologia |
|---|---|
| API | Python 3.12 · FastAPI · SQLAlchemy 2 (async) · Alembic |
| Banco | PostgreSQL 17 |
| Cache / rate limit / lock | Redis 7 |
| Web | Next.js 16 (App Router) · TypeScript · Tailwind CSS 4 |
| Testes | pytest + respx · Vitest |
| Empacotamento | Docker Compose |

Sobre a troca de React+Vite por Next.js, pedida pelo item 70 do documento original:
justificativa em [`docs/00-arquitetura.md`](docs/00-arquitetura.md) §4. O backend é
idêntico nos dois cenários — reverter custa pouco agora e muito depois.

---

## Subir o projeto

Requisito: Docker com Compose v2 (`docker compose version` ≥ 2.20).

```bash
cd albion-economy
cp .env.example .env          # edite POSTGRES_PASSWORD e AODP_USER_AGENT
docker compose up -d --build
docker compose ps
```

Espere todos os serviços aparecerem como `healthy` ou `running`. Primeira subida
demora alguns minutos (build das imagens + `npm install`).

### Verificar

```bash
curl -s http://localhost:8000/health            | python3 -m json.tool
curl -s http://localhost:8000/health/database   | python3 -m json.tool
curl -s http://localhost:8000/health/aodp       | python3 -m json.tool
curl -s http://localhost:8000/api/v1/meta       | python3 -m json.tool
```

Resposta esperada de `/health/database` com a stack de pé:

```json
{
  "status": "ok",
  "database": { "status": "ok", "latency_ms": 3, "detail": null },
  "cache":    { "status": "ok", "latency_ms": 1, "detail": null }
}
```

Depois abra:

| URL | O quê |
|---|---|
| http://localhost:3000 | Painel de estado do pipeline |
| http://localhost:8000/docs | Swagger (OpenAPI) |
| http://localhost:8000/redoc | ReDoc |

### Aplicar o schema e importar o catálogo

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.cli.import_items
```

O `upgrade head` cria as tabelas e semeia servidores, locais, fontes de dado e
parâmetros de configuração. O import baixa ~40 MB do `ao-bin-dumps` e leva alguns
segundos; roda separado das migrations de propósito, porque subir o schema não
pode depender de rede.

Saída esperada do import:

```
names_loaded            12237
metadata_entries         6049
categories_upserted        16
items_upserted          12237
items_without_metadata    266
items_without_tier        165
items_tracked             312
invalid_names               0
```

`items_without_metadata` e `items_without_tier` não são erro: são itens que o dump
não descreve (baús de journal, tesouros, alguns consumíveis). Eles entram no
catálogo com os campos em NULL, porque inventar tier ou peso seria pior do que
não ter (requisito 52).

Conferir:

```bash
curl -s "http://localhost:8000/api/v1/meta" | python3 -m json.tool
curl -s "http://localhost:8000/api/v1/items?search=couro&tier=5&limit=5" | python3 -m json.tool
curl -s "http://localhost:8000/api/v1/items?tracked_only=true&limit=1" | python3 -m json.tool
```

Reimportar depois de um patch do jogo é seguro: o UPSERT atualiza nome, peso e
categoria sem recriar a linha, e `items.id` continua o mesmo — é para ele que os
preços e o histórico apontam. A marcação `is_tracked` é preservada, porque é
decisão operacional e não metadado do jogo; para reaplicar a lista padrão:

```bash
docker compose exec backend python -m app.cli.import_items --apply-tracking
```

### Coletar preços

```bash
# uma passada
docker compose exec backend python -m app.cli.collect_market --server west

# worker contínuo (perfil separado: coleta é processo longo)
docker compose --profile collector up -d worker-market
docker compose --profile collector logs -f worker-market
```

A coleta varre os itens marcados como `is_tracked` (312 por padrão) nos 8 locais
e nas 5 qualidades. Um lock no Redis impede dois collectors do mesmo servidor —
eles não corromperiam dado, mas dobrariam o consumo de rate limit, e o orçamento
é de 1 requisição por segundo.

Depois:

```bash
curl -s "http://localhost:8000/api/v1/market/prices?server=west&search=couro&limit=5" \
  | python3 -m json.tool
```

e abra http://localhost:3000/market.

A tela mostra, por linha, as duas pontas do mercado separadas ("o que você paga"
e "o que você recebe"), a idade de cada cotação, a mediana de 30 dias com a
distância do preço atual, e o giro do item com a cobertura do histórico. Preço
fresco num mercado com 3 dias de registro em 30 é frágil — a tela diz isso.

Acompanhar execuções:

```bash
docker compose exec postgres psql -U albion -d albion -c \
  "SELECT collector, status, rows_upserted, rows_rejected, http_requests, started_at
   FROM collector_runs ORDER BY started_at DESC LIMIT 5;"
```

### Coletar histórico e gold

```bash
docker compose exec backend python -m app.cli.collect_history --server west --days 30
docker compose exec backend python -m app.cli.collect_history --gold --server west
```

Frequência baixa de propósito: o bucket é de hora ou de dia, e recoletar de
minuto em minuto gasta cota sem gerar informação nova.

A marcação de outlier roda depois da gravação, com a janela inteira à vista. O
valor suspeito **não é apagado** — ele aparece no gráfico como círculo vazado e
fica fora das estatísticas do período.

### Testes

```bash
docker compose exec backend pytest -q
docker compose exec backend ruff check .
docker compose exec frontend npm run test
docker compose exec frontend npm run typecheck
```

Os testes em `backend/tests/integration/` precisam de PostgreSQL e usam um banco
separado (`albion_test`). Quando o banco não está disponível eles **pulam**, com a
razão impressa — nunca passam fingindo ter testado:

```bash
docker compose exec backend pytest -q -rs
```

### Logs e manutenção

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose restart backend
docker compose down          # para tudo, mantém os dados
docker compose down -v       # para tudo e APAGA os volumes
```

Há atalhos equivalentes no `Makefile` (`make up`, `make test`, `make logs`, …).

### Rodar sem Docker

```bash
# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+asyncpg://albion:SENHA@localhost:5432/albion
export REDIS_URL=redis://localhost:6379/0
uvicorn app.main:app --reload --port 8000

# frontend (outro terminal)
cd frontend
npm install
BACKEND_INTERNAL_URL=http://localhost:8000 npm run dev
```

---

## Estrutura

```
albion-economy/
├── backend/
│   ├── app/
│   │   ├── api/v1/          rotas HTTP (nada de regra de negócio aqui)
│   │   ├── core/            config, logging, frescor do dado
│   │   ├── db/ cache/       engine PostgreSQL, cliente Redis
│   │   ├── models/          tabelas SQLAlchemy
│   │   ├── repositories/    acesso a dados (queries ficam só aqui)
│   │   ├── catalog/         parser e importador do catálogo de itens
│   │   ├── collectors/aodp/ client do AODP: batching, rate limit, normalização
│   │   ├── cli/             comandos operacionais (import_items)
│   │   ├── services/        orquestração
│   │   ├── calculations/    funções PURAS de taxa/lucro   (FASE 6+)
│   │   ├── opportunities/   motor de score                (FASE 6+)
│   │   ├── collectors/      client AODP e coleta          (FASE 3+)
│   │   └── integrations/    ping de disponibilidade do AODP
│   ├── alembic/             migrations
│   └── tests/
├── frontend/src/
│   ├── app/                 rotas do App Router
│   ├── components/          UI
│   └── lib/                 acesso ao backend (server-only) e formatação
├── workers/                 pontos de entrada dos processos longos (FASE 3+)
├── database/                seeds
└── docs/                    arquitetura, modelo de dados, AODP, riscos e fases
```

---

## Regras que o projeto não quebra

1. **O frontend nunca chama o AODP.** O caminho é
   `Browser → Next → FastAPI → Redis/PostgreSQL → AODP`.
2. **Cálculo é do backend.** `calculations/` é puro: entra número, sai número, sem I/O.
3. **Ausência de dado é `NULL`/`UNKNOWN`, nunca `0`.** Preço zero e falta de cotação são
   coisas diferentes; confundi-los inventa lucro que não existe.
4. **Taxa nunca é hardcode.** Vive em `config_parameters`.
5. **Segredo nunca é commitado.** Só `.env.example` entra no repositório.
6. **Rate limit do AODP é respeitado.** 180/min *e* 300/5min — o segundo é o que
   manda: 1 requisição por segundo sustentada.
7. **Toda mudança de schema passa por migration.** Nada de `create_all()` em produção.
8. **Collector não roda em serverless.**

---

## Sobre a fonte de dados

Os preços vêm do **Albion Online Data Project**, um projeto comunitário: o dado existe
porque algum jogador abriu aquele mercado no jogo com o client de coleta rodando.

Consequência prática: nenhuma cotação é garantida, e mercado pouco visitado tem dado
velho ou nenhum. Por isso toda tela mostra a idade do dado e o sistema trata liquidez
desconhecida como um estado legítimo, não como erro.

Este projeto não é afiliado a Albion Online nem à Sandbox Interactive GmbH.

---

## O client do AODP (fase 3)

`backend/app/collectors/aodp/` — quatro módulos com responsabilidades separadas:

| Módulo | O quê |
|---|---|
| `schemas.py` | contrato das respostas, validação estrita |
| `batching.py` | divide itens em lotes pelo **comprimento da URL final** |
| `rate_limit.py` | janela dupla, backoff exponencial com jitter, `Retry-After` |
| `normalization.py` | funções puras: payload validado → registro pronto para o banco |
| `client.py` | HTTP, retry, cache, captura do payload bruto |

Decisões que valem registro:

- **A janela de 5 minutos é a que manda.** 300/5min são 1 req/s sustentado. Quem
  implementa só os 180/min passa no teste curto e toma 429 no minuto três. Há um
  teste dedicado a impedir essa regressão.
- **Lote fechado por comprimento de URL**, não por contagem de itens:
  `T8_2H_HOLYSTAFF_MORGANA@3` ocupa quase quatro vezes mais que `T4_BAG`.
  A medição é feita na URL já codificada, porque `Fort Sterling` vira
  `Fort%20Sterling`.
- **`Retry-After` tem prioridade sobre o backoff.** O servidor sabe melhor.
- **4xx que não é 429 não é repetido.** É erro nosso; repetir só gasta a cota de
  quem está usando a API direito.
- **Payload fora do contrato falha alto**, com o bruto preservado na exceção.
  Aceitar formato diferente em silêncio grava dado errado no banco (risco R8).
- **Cache fora do ar não derruba coleta.** Perder cache custa requisição; perder
  coleta custa o dia.
- **Relógio e espera são injetados**, então os testes verificam comportamento de
  5 minutos em milissegundos, sem `sleep` de verdade.

O client não toca no banco. Ele devolve objetos validados; persistir é trabalho
do collector, na fase 4.

## Próximo passo

**FASE 4 — collector de mercado.** Agendamento, lock no Redis para não rodar dois
collectors do mesmo servidor, upsert em `market_prices`, registro em
`collector_runs` e `raw_responses`, endpoint `GET /api/v1/market/prices` e a tela
`/market` com idade do dado e ordenação.

O plano completo está em [`docs/03-riscos-e-fases.md`](docs/03-riscos-e-fases.md).
