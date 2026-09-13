# 03 — Riscos técnicos e plano de fases

## Riscos

Ordenados por dano × probabilidade.

### R1 — Confiar em dado velho ou ausente *(alto / alto)*
Coleta comunitária: muito item/cidade tem cotação de horas ou dias atrás. Uma
"oportunidade" calculada sobre dado morto faz o usuário perder prata — e a confiança no
produto morre no primeiro prejuízo.
**Mitigação:** idade por campo visível em toda tela; `confidence` na oportunidade;
score penaliza frescor ruim; abaixo de um limiar configurável a oportunidade nem é
publicada.

### R2 — Outlier de média contaminando tendência *(alto / alto)*
Demonstrado na validação: 3.6k → 29.7k → 3.7k em dias consecutivos. O endpoint devolve
média, não mediana.
**Mitigação:** mediana + MAD, flag `is_outlier`, médias de referência por mediana.

### R3 — Rate limit / ban *(alto / médio)*
300 req/5min = 1 req/s sustentado. Um loop ingênuo estoura em segundos e o projeto é
compartilhado por toda a comunidade.
**Mitigação:** limiter de janela dupla, batching por comprimento de URL, backoff
exponencial com jitter, lock no Redis para não rodar dois collectors, gzip, User-Agent
identificável.

### R4 — Taxa/fórmula errada no cálculo *(alto / médio)*
Return rate, station fee e imposto premium mudam com patch e com estação/cidade. Um
número errado invalida crafting, refino e focus de uma vez.
**Mitigação:** tudo em `config_parameters`; `calculations/` puro e coberto por teste com
casos conhecidos; enquanto não houver valor verificado, retornar `UNKNOWN` (requisito 52).

### R5 — Explosão de cardinalidade *(médio / alto)*
itens × 8 tiers × 5 encantos × 5 qualidades × 8 locais × 3 servidores é grande demais
para varrer inteiro com 1 req/s.
**Mitigação:** catálogo priorizado (recursos refinados e itens líquidos primeiro),
frequência por tier de interesse, `items.active` como chave de coleta.

### R6 — Collector em serverless *(alto / baixo — se a arquitetura for respeitada)*
Vercel mata processos longos. Collector lá = coleta parcial e rate limit descontrolado.
**Mitigação:** collectors em container long-running, fora da Vercel. Item 71 já aponta
isso; o risco é alguém "simplificar" depois.

### R7 — Regra de negócio vazando pro frontend *(médio / alto)*
Sempre começa com "é só um cálculo de margem no componente". Depois há duas fórmulas
divergentes.
**Mitigação:** `calculations/` só no backend; teste de arquitetura no CI que falha se
`frontend/src` contiver aritmética de taxa/lucro.

### R8 — Mudança de contrato no AODP *(médio / baixo)*
`city` vs `location` já difere entre endpoints hoje.
**Mitigação:** schemas Pydantic estritos no client; payload cru em `raw_responses`;
alerta quando taxa de rejeição na validação sobe.

### R9 — Lock-in de Supabase *(baixo / médio)*
Item 47 pede portabilidade.
**Mitigação:** só PostgreSQL padrão + Alembic. Sem RLS, sem `auth.users`, sem Edge
Functions no caminho crítico. Auth/Storage do Supabase, se entrarem, ficam atrás de uma
interface.

### R10 — Custo de infraestrutura antes da receita *(médio / médio)*
**Mitigação:** Vercel free/hobby + Postgres gerenciado free tier + Redis free tier +
um container pequeno para API+workers. Alvo: MVP abaixo de US$ 15/mês.

---

## Fases

Cada fase termina com: testes verdes, comandos documentados, e uma decisão explícita de
seguir. Sem pular (requisito 51).

| Fase | Entrega | Critério de conclusão |
|---|---|---|
| **0** | Arquitetura, modelo, validação do AODP, riscos | Estes documentos ✔ |
| **1** | Infra: Docker, PG, Redis, FastAPI, Next.js, `.env`, README, testes | `docker compose up` sobe tudo; `/health` verde nos 3 checks; testes passam ✔ |
| **2** | Migrations + seed + catálogo de itens | `alembic upgrade head` idempotente; 12.237 itens importados do `ao-bin-dumps` ✔ |
| **3** | Client AODP: prices, history, gold + limiter, retry, batch, cache | 122 testes verdes, zero chamada real à API ✔ |
| **4** | Collector, normalização, `/api/v1/market/prices` e tela `/market` | Preço na tela com idade por campo e ordenação ✔ |
| **5** | History, `/market/history` com gráfico, `/gold` | Outliers marcados e fora da estatística; mediana como referência ✔ |
| **6** | Opportunity Engine v1 + `/arbitrage` | Custo, taxa, transporte, lucro, margem, ROI, score |
| **7** | Receitas + `/crafting` | Retorno de material, taxa de estação, focus |
| **8** | `/refining` | Prata/focus por refino |
| **9** | Ranking de focus | Ordenação por `profit_per_focus` |
| **10** | Dashboard integrado | Cards + Top Oportunidades |

Fases posteriores (não planejadas em detalhe agora): contas, entitlements, licenças,
API keys, pagamento, admin, alertas.

**Estado atual: Fases 1 a 8 implementadas. As taxas do jogo continuam sem medição (`docs/04-taxas.md`), mas deixaram de ser bloqueio: são entrada do usuário.**
