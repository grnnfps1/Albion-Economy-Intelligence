# workers/

Processos de longa duração, separados da API.

| Worker | Fase | Papel |
|---|---|---|
| `market_collector` | 4 | varre preços atuais do AODP e faz upsert em `market_prices` |
| `history_collector` | 5 | busca buckets de histórico |
| `opportunity_worker` | 6 | recalcula `opportunities` e scores |

Regra que não pode ser quebrada: **collector não roda em função serverless**
(item 71). Ele mantém estado — cursor de itens, janela de rate limit, backoff.
Um ambiente que mata o processo no meio produz coleta parcial e estouro de rate
limit. Ver `docs/00-arquitetura.md` §3.

O código compartilhado (client do AODP, normalização, repositórios) fica em
`backend/app/`; estes processos são só pontos de entrada, para que API e worker
nunca divirjam na regra de negócio.
