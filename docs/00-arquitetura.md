# 00 — Arquitetura

> Documento da FASE 0. Define decisões estruturais antes de escrever código de negócio.

## 1. Princípio

O sistema não é um "site de preços". É um pipeline de dados com uma camada de
apresentação acoplada no fim. A ordem de importância é:

```
correção do dado  >  correção do cálculo  >  performance  >  quantidade de telas
```

Toda regra de negócio vive no backend. O frontend renderiza e filtra — nunca calcula
lucro, margem, ROI ou score.

## 2. Camadas

```
┌──────────────────────────────────────────────────────────────┐
│  AODP  (west / east / europe)          ao-bin-dumps (GitHub) │
└───────┬──────────────────────────────────────┬───────────────┘
        │ HTTP (gzip, rate-limited)            │ HTTP (metadata, raro)
┌───────▼──────────────────────────────────────▼───────────────┐
│  COLLECTORS  (processo long-running, fora da Vercel)         │
│  · scheduler   · rate limiter   · retry/backoff              │
│  · raw_responses (auditoria)                                 │
└───────┬──────────────────────────────────────────────────────┘
        │ payload bruto
┌───────▼──────────────────────────────────────────────────────┐
│  NORMALIZATION                                               │
│  · sentinelas → NULL   · naive UTC → timestamptz              │
│  · location string → location_id   · outlier flagging        │
└───────┬──────────────────────────────────────────────────────┘
┌───────▼──────────────────────────────────────────────────────┐
│  POSTGRESQL   (dados públicos + dados privados separados)     │
└───────┬──────────────────────────────────────────────────────┘
┌───────▼──────────────────────────────────────────────────────┐
│  CALCULATION ENGINE   (funções puras, sem I/O)               │
│  taxas · lucro · margem · ROI · focus · liquidez             │
└───────┬──────────────────────────────────────────────────────┘
┌───────▼──────────────────────────────────────────────────────┐
│  OPPORTUNITY ENGINE   (worker; materializa `opportunities`)   │
└───────┬──────────────────────────────────────────────────────┘
┌───────▼──────────────────────────────────────────────────────┐
│  FASTAPI  /api/v1     ← Redis cache · rate limit · entitlements│
└───────┬──────────────────────────────────────────────────────┘
┌───────▼──────────────────────────────────────────────────────┐
│  WEB APP  (Next.js na Vercel)                                 │
└──────────────────────────────────────────────────────────────┘
```

### Regra de dependência

`api → services → repositories → db` e `services → calculations`.

`calculations/` é a única pasta obrigatoriamente **pura**: entra número, sai número.
Sem SQLAlchemy, sem `httpx`, sem `datetime.now()` implícito. Isso é o que torna o
motor testável sem banco e sem rede (requisito 43).

## 3. Processos em produção

| Processo | Papel | Onde roda | Por quê |
|---|---|---|---|
| `web` | Next.js | Vercel | SSR/ISR + CDN |
| `api` | FastAPI | container 24/7 (Fly.io / Railway / Render) | precisa de conexão persistente ao PG |
| `worker-market` | coleta de preços | mesmo host da API, processo separado | loop contínuo |
| `worker-history` | coleta de histórico | idem | job periódico |
| `worker-opportunity` | recalcula scores | idem | CPU-bound, não pode bloquear a API |
| `postgres` | dados | Neon / Supabase / RDS | — |
| `redis` | cache + rate limit + lock de scheduler | Upstash / Redis Cloud | — |

**Não colocar collector em função serverless.** Um collector é um loop com estado
(cursor de itens, janela de rate limit, backoff). Serverless mata o processo, perde a
janela e o resultado é ou dado faltando ou ban por excesso de requisição.

## 4. Decisão de stack: Next.js em vez de React + Vite

O documento (item 70) pede avaliação explícita. Recomendação: **trocar React+Vite por
Next.js (App Router) apenas na camada web.** Todo o resto do stack fica como
especificado.

**Por que trocar**

1. **SEO é canal de aquisição real.** Buscas como "preço couro T5 albion" ou
   "albion t6 refining calculator" têm volume. Uma SPA Vite entrega HTML vazio; páginas
   de item/cidade renderizadas no servidor com ISR são indexáveis. Para um produto que
   quer vender assinatura (itens 76–78), tráfego orgânico é o funil mais barato.
2. **Vercel é o host nativo do Next.** ISR, edge cache, revalidação por tag e preview
   deploys funcionam sem configuração. Vite na Vercel vira um bucket estático — funciona,
   mas você paga a complexidade de CDN/cache na mão.
3. **Route Handlers protegem o backend.** O browser fala com `/api/proxy/*` do Next;
   o Next fala com o FastAPI usando um token de serviço. A URL e as credenciais do backend
   nunca chegam ao cliente. Com SPA pura, o backend fica exposto na origem.
4. **Sessão/entitlements (itens 59–65)** pedem middleware server-side. O Next já tem.

**Por que isso NÃO viola a regra 54**

A regra é "frontend não chama o AODP direto". Mantida:
`Browser → Next (render/proxy) → FastAPI → Redis/Postgres → AODP`.
O Next não ganha regra de negócio. Ele renderiza e encaminha. Se algum cálculo aparecer
dentro de `frontend/`, é bug de arquitetura, não feature.

**Custo da troca**

Baixo agora, alto depois. A Fase 1 entrega só o shell de layout + página de status —
migrar hoje custa minutos. Depois de 8 telas prontas, custa dias. Por isso a decisão
precisa sair agora.

**Se você preferir manter Vite:** o backend não muda em nada. Diga e eu troco
`frontend/` por Vite mantendo tudo o mais idêntico.

## 5. Cache (Redis)

Três usos distintos, com prefixos separados para não colidirem:

| Prefixo | Conteúdo | TTL |
|---|---|---|
| `cache:v1:*` | respostas de endpoints de leitura | 30–300 s, configurável |
| `rate:aodp:*` | janela deslizante do rate limit do AODP | 60 s / 300 s |
| `lock:collector:*` | lock distribuído para não rodar dois collectors iguais | TTL = duração do job |

O TTL do cache nunca pode ser maior que a frequência de coleta — senão o usuário vê dado
mais velho do que o banco tem.

## 6. Ambiente

`ENVIRONMENT` ∈ `development | staging | production`.

Em `development`, respostas da API carregam `X-Data-Mode: mock` quando qualquer fonte
for mock. Em `production` a aplicação **recusa subir** se alguma fonte mock estiver
habilitada (requisito 44). Isso é um `assert` no startup, não uma convenção.

## 7. Versionamento de API

Tudo sob `/api/v1`. Quebra de contrato cria `/api/v2` — nunca altera `v1` em silêncio.
`/health*` fica fora do prefixo versionado (infra, não contrato de produto).
