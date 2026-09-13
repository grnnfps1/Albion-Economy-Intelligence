# Albion Economy Intelligence

Motor de inteligência econômica para Albion Online. Transforma os dados de mercado do
Albion Online Data Project em oportunidades acionáveis: arbitragem, crafting,
refinamento e prata por Focus.

**Estado: as dez fases do plano original estão concluídas.** A plataforma coleta
preços e histórico do AODP, marca outliers, e entrega `/market`,
`/market/history`, `/gold`, `/arbitrage`, `/crafting`, `/refining`, `/focus` e o
painel integrado em `/`.

Imposto de venda, retorno de material e taxa de estação são **entrada do
usuário** — nenhum é constante, e uma calculadora que os fixa está errada para
quase todo mundo. Sem eles, a resposta é `UNKNOWN` com o motivo, nunca um número
calculado com taxa zero.

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

Sobre a troca de React+Vite por Next.js, pedida pelo item 70 do documento
original: justificativa em [`docs/00-arquitetura.md`](docs/00-arquitetura.md) §4.

---

## Subir o projeto

Requisito: Docker com Compose v2 (`docker compose version` maior ou igual a 2.20).

```bash
cp .env.example .env          # edite POSTGRES_PASSWORD e AODP_USER_AGENT
docker compose up -d --build
docker compose ps
```

Espere todos os serviços aparecerem como `healthy` ou `running`. A primeira
subida demora alguns minutos: build das imagens e `npm install`.

### 1. Schema e catálogo

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.cli.import_items
```

O `upgrade head` cria as tabelas e semeia servidores, locais, fontes de dado e
parâmetros. O import baixa cerca de 40 MB do `ao-bin-dumps`; roda separado das
migrations de propósito, porque subir o schema não pode depender de rede.

Saída esperada:

```
catálogo
  names_loaded            12237
  items_upserted          12237
  items_without_metadata    266
  items_tracked             312

receitas
  items_with_recipes       9677
  recipes_upserted        12515
  materials_upserted      27899
```

`items_without_metadata` não é erro: são itens que o dump não descreve (journals,
tesouros, alguns consumíveis). Entram com os campos em `NULL`, porque inventar
tier ou peso seria pior do que não ter.

Reimportar depois de um patch do jogo é seguro: o UPSERT atualiza nome, peso e
categoria sem recriar a linha, e `items.id` continua o mesmo — é para ele que os
preços apontam. A marcação `is_tracked` é preservada por ser decisão
operacional; para reaplicar a lista padrão, use `--apply-tracking`.

### 2. Coletar

```bash
# preços, uma passada
docker compose exec backend python -m app.cli.collect_market --server west

# histórico e gold (frequência baixa: o bucket é de hora ou de dia)
docker compose exec backend python -m app.cli.collect_history --server west --days 30
docker compose exec backend python -m app.cli.collect_history --gold --server west

# worker contínuo de preços
docker compose --profile collector up -d worker-market
docker compose --profile collector logs -f worker-market
```

A coleta varre os itens `is_tracked` (312 por padrão) nos 8 locais e nas 5
qualidades. Um lock no Redis impede dois collectors do mesmo servidor: eles não
corromperiam dado, mas dobrariam o consumo de rate limit, e o orçamento é de 1
requisição por segundo.

A marcação de outlier roda depois da gravação, com a janela inteira à vista. O
valor suspeito **não é apagado** — aparece no gráfico como círculo vazado e fica
fora das estatísticas.

### 3. Usar

| URL | O quê |
|---|---|
| http://localhost:3000 | Painel integrado |
| http://localhost:3000/status | Estado do pipeline |
| http://localhost:8000/docs | Swagger (OpenAPI) |
| http://localhost:8000/redoc | ReDoc |

**Configure as taxas na primeira visita.** O formulário está no topo do painel.
Sem elas o sistema mostra `UNKNOWN` em vez de lucro, de propósito.

### Verificar

```bash
curl -s http://localhost:8000/health/database | python3 -m json.tool
curl -s "http://localhost:8000/api/v1/market/prices?server=west&search=couro&limit=5" | python3 -m json.tool
```

Resposta esperada de `/health/database` com a stack de pé:

```json
{
  "status": "ok",
  "database": { "status": "ok", "latency_ms": 3, "detail": null },
  "cache":    { "status": "ok", "latency_ms": 1, "detail": null }
}
```

Acompanhar execuções dos collectors:

```bash
docker compose exec postgres psql -U albion -d albion -c \
  "SELECT collector, status, rows_upserted, rows_rejected, http_requests, started_at
   FROM collector_runs ORDER BY started_at DESC LIMIT 5;"
```

### Testes

```bash
docker compose exec backend pytest -q -rs
docker compose exec backend ruff check .
docker compose exec frontend npm run test
docker compose exec frontend npm run typecheck
```

Os testes em `backend/tests/integration/` precisam de PostgreSQL e usam o banco
`albion_test`. Sem banco eles **pulam**, com a razão impressa — nunca passam
fingindo ter testado. O `-rs` mostra os skips.

### Logs e manutenção

```bash
docker compose logs -f backend
docker compose restart backend
docker compose down          # para tudo, mantém os dados
docker compose down -v       # para tudo e APAGA os volumes
```

Há atalhos equivalentes no `Makefile` (`make up`, `make test`, `make collect`).

### Rodar sem Docker

```bash
# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+asyncpg://albion:SENHA@localhost:5432/albion
export REDIS_URL=redis://localhost:6379/0
uvicorn app.main:app --reload --port 8000

# frontend, em outro terminal
cd frontend
npm install
BACKEND_INTERNAL_URL=http://localhost:8000 npm run dev
```

---

## Estrutura

```
albion-economy/
├── backend/app/
│   ├── api/v1/          rotas HTTP (nada de regra de negócio aqui)
│   ├── core/            config, logging, frescor do dado
│   ├── db/ cache/       engine PostgreSQL, cliente Redis, lock distribuído
│   ├── models/          tabelas SQLAlchemy
│   ├── repositories/    acesso a dados (queries ficam só aqui)
│   ├── catalog/         parser e importador de itens e receitas
│   ├── collectors/      client do AODP e os collectors de mercado e histórico
│   ├── calculations/    funções PURAS: taxas, estatística, cadeia, focus
│   ├── opportunities/   motor de arbitragem e score
│   ├── services/        orquestração
│   ├── cli/             comandos operacionais
│   └── integrations/    ping de disponibilidade do AODP
├── backend/alembic/     migrations
├── backend/tests/       unitários e integration/
├── frontend/src/
│   ├── app/             rotas do App Router
│   ├── components/      UI
│   └── lib/             acesso ao backend (server-only) e formatação
├── workers/             pontos de entrada dos processos longos
├── database/            seeds
└── docs/                arquitetura, modelo de dados, AODP, riscos, taxas
```

---

## Regras que o projeto não quebra

1. **O frontend nunca chama o AODP.** O caminho é
   `Browser → Next → FastAPI → Redis/PostgreSQL → AODP`.
2. **Cálculo é do backend.** `calculations/` é puro: entra número, sai número,
   sem I/O e sem relógio implícito.
3. **Ausência de dado é `NULL`/`UNKNOWN`, nunca `0`.** Preço zero e falta de
   cotação são coisas diferentes; confundi-los inventa lucro que não existe.
4. **Taxa nunca é hardcode.** Vem do usuário, ou de `config_parameters`, ou é
   `UNKNOWN`.
5. **Segredo nunca é commitado.** Só `.env.example` entra no repositório.
6. **Rate limit do AODP é respeitado.** 180/min **e** 300/5min — o segundo é o
   que manda: 1 requisição por segundo sustentada.
7. **Toda mudança de schema passa por migration.** Nada de `create_all()` fora de
   teste.
8. **Collector não roda em serverless.**

Detalhamento e armadilhas conhecidas em [`CLAUDE.md`](CLAUDE.md).

---

## O client do AODP

`backend/app/collectors/aodp/` — cinco módulos com responsabilidades separadas:

| Módulo | O quê |
|---|---|
| `schemas.py` | contrato das respostas, validação estrita |
| `batching.py` | divide itens em lotes pelo comprimento da URL final |
| `rate_limit.py` | janela dupla, backoff com jitter, `Retry-After` |
| `normalization.py` | funções puras: payload validado vira registro de banco |
| `client.py` | HTTP, retry, cache, captura do payload bruto |

Decisões que valem registro:

- **A janela de 5 minutos é a que manda.** 300/5min são 1 req/s sustentado. Quem
  implementa só os 180/min passa no teste curto e toma 429 no minuto três. Há
  teste dedicado a impedir essa regressão.
- **Lote fechado por comprimento de URL**, não por contagem de itens:
  `T8_2H_HOLYSTAFF_MORGANA@3` ocupa quase quatro vezes mais que `T4_BAG`. A
  medição usa a URL já codificada, porque `Fort Sterling` vira `Fort%20Sterling`.
- **`Retry-After` tem prioridade sobre o backoff.** O servidor sabe melhor.
- **4xx que não é 429 não é repetido.** É erro nosso; repetir só gasta a cota de
  quem está usando a API direito.
- **Payload fora do contrato falha alto**, com o bruto preservado na exceção.
  Aceitar formato diferente em silêncio grava dado errado no banco.
- **Cache fora do ar não derruba coleta.** Perder cache custa requisição; perder
  coleta custa o dia.

---

## Sobre a fonte de dados

Os preços vêm do **Albion Online Data Project**, um projeto comunitário: o dado
existe porque algum jogador abriu aquele mercado no jogo com o client de coleta
rodando.

Consequência prática: nenhuma cotação é garantida, e mercado pouco visitado tem
dado velho ou nenhum. Por isso toda tela mostra a idade do dado, e liquidez
desconhecida é um estado legítimo — não um erro.

O histórico do AODP é agregado por **média**, e uma única ordem manipulada
contamina o bucket. Visto no dado real: 3.625, depois 29.790, depois 3.737 em
dias consecutivos. Por isso as estatísticas usam mediana e os outliers ficam
marcados e visíveis, em vez de apagados.

Este projeto não é afiliado a Albion Online nem à Sandbox Interactive GmbH.

---

## O que falta

Nada disso bloqueia o que existe:

1. **Medir as taxas no jogo.** Roteiro em [`docs/04-taxas.md`](docs/04-taxas.md):
   seis medições, incluindo se token de facção retorna no craft. Define o valor
   pré-preenchido para quem não quiser configurar nada.
2. **Contas e preferências.** Hoje os parâmetros do usuário vivem na URL. Com
   login viram preferência salva; o cálculo não muda.
3. **Watchlist e alertas.** A arquitetura está preparada; falta a tabela e o
   worker que avalia condições.
4. **Portfólio.** Comparar o lucro previsto com o realizado — é o que fecharia o
   ciclo do produto.
