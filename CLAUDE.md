# CLAUDE.md

Contexto para agentes trabalhando neste repositório. Leia antes de escrever código.

## O que é

Plataforma de inteligência econômica para Albion Online. Não é um site de preços:
é um pipeline de dados que transforma cotações de mercado em oportunidades
acionáveis (arbitragem, crafting, refino, prata por Focus).

A pergunta que o produto responde: **"onde está o dinheiro no Albion agora?"**

Não basta mostrar "Couro T5 custa 1.200". O alvo é: "Couro T5 está 14% abaixo da
média de 7 dias em Caerleon, vendável em Lymhurst com margem de 18,4% e score 91".

## Estado atual

| Fase | O quê | Status |
|---|---|---|
| 0 | Arquitetura, modelo de dados, validação do AODP | ✅ |
| 1 | Infra: Docker, Postgres, Redis, FastAPI, Next.js | ✅ |
| 2 | Migrations, seed, catálogo de 12.237 itens | ✅ |
| 3 | Client do AODP: rate limit, batching, retry, normalização | ✅ |
| 4 | Collector de mercado + `/api/v1/market/prices` + tela `/market` | ✅ |
| 5 | Histórico, outliers, gráficos, gold | ✅ |
| 6 | Opportunity Engine + arbitragem | ⛔ bloqueada: taxas não verificadas |
| 7–10 | Crafting, refino, Focus, dashboard | ⬜ |

Detalhe das fases em `docs/03-riscos-e-fases.md`.

**A coleta existe e grava preço.** `python -m app.cli.collect_market --server west`
faz uma passada; com `--loop` vira o worker contínuo. A tela `/market` mostra o
resultado com a idade de cada cotação.

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2 async · Alembic · PostgreSQL 17 · Redis 7 ·
Next.js 16 App Router · TypeScript · Tailwind 4 · pytest + respx · Vitest · Docker Compose.

Next.js foi escolhido no lugar de React+Vite por causa de SEO, Vercel e sessão
server-side. A justificativa está em `docs/00-arquitetura.md` §4. Não reverta sem
ler.

## Regras invioláveis

Estas não são preferências de estilo. Quebrar qualquer uma gera dado errado ou
decisão errada do usuário.

1. **Ausência de dado é `NULL`/`UNKNOWN`, nunca `0`.**
   O AODP sinaliza "não há ordem" com preço `0` e data `0001-01-01T00:00:00`.
   Tratar isso como preço zero produz margem infinita e a plataforma anuncia uma
   oportunidade que não existe. Ver `collectors/aodp/normalization.py`.

2. **Nunca inventar número.** Taxa, receita, preço, liquidez: se não foi
   verificado, o valor fica `NULL` com `source = 'UNKNOWN'` em
   `config_parameters`. Há teste que falha se alguém preencher com chute.

3. **Cálculo é do backend.** `app/calculations/` é puro: entra número, sai
   número, sem SQLAlchemy, sem httpx, sem `datetime.now()` implícito. Nenhuma
   aritmética de taxa, lucro, margem ou ROI pode aparecer em `frontend/src`.

4. **O frontend nunca chama o AODP.** O caminho é
   `Browser → Next → FastAPI → Redis/Postgres → AODP`.

5. **Taxa nunca é hardcode.** Vive em `config_parameters` e chega às funções de
   cálculo como argumento.

6. **Rate limit do AODP: 180/min E 300/5min.** O segundo é o que manda — são
   1 req/s sustentado. Quem implementa só a janela de 1 minuto passa no teste
   curto e toma 429 no minuto três. Há teste dedicado a impedir essa regressão.

7. **Buy e sell são coisas diferentes.** Quem compra do mercado paga
   `sell_price_min`; quem vende na hora recebe `buy_price_max`. Trocar inverte o
   sinal do lucro.

8. **Toda mudança de schema passa por migration.** Nunca `create_all()` fora de
   teste.

9. **Segredo nunca é commitado.** Só `.env.example` entra no repositório.

10. **Collector não roda em serverless.** Ele mantém estado (cursor de itens,
    janela de rate limit, backoff). Um ambiente que mata o processo no meio
    produz coleta parcial e estouro de rate limit.

11. **Testes não chamam a API externa.** Nunca. Use `respx` e payloads fiéis.

## Arquitetura em uma tela

```
AODP (west/east/europe)          ao-bin-dumps (catálogo, GitHub)
      │                                 │
      ▼                                 ▼
 collectors/aodp  ──► normalization ──► PostgreSQL
      │                                 │
      │                          calculations (puro)
      │                                 │
      │                          opportunities (worker)
      ▼                                 ▼
                              FastAPI /api/v1  ◄── Redis (cache, rate, lock)
                                        │
                                  Next.js (Vercel)
```

Dependência: `api → services → repositories → db` e `services → calculations`.
Query SQL só existe em `repositories/`. Rota HTTP não tem regra de negócio.

## Layout

```
backend/app/
  api/v1/routes/     rotas HTTP
  core/              config, logging, frescor do dado
  db/ cache/         engine Postgres, cliente Redis
  models/            tabelas SQLAlchemy
  repositories/      queries (único lugar com SQL)
  catalog/           parser + importador do catálogo de itens
  collectors/aodp/   client do AODP
  calculations/      funções puras de taxa/lucro     (fase 6+)
  opportunities/     motor de score                  (fase 6+)
  cli/               comandos operacionais
frontend/src/
  app/               rotas do App Router
  components/        UI
  lib/               acesso ao backend (server-only) e formatação
docs/                arquitetura, modelo de dados, AODP, riscos e fases
```

## Comandos

```bash
# subir
cp .env.example .env
docker compose up -d --build

# banco
docker compose exec backend alembic upgrade head
docker compose exec backend alembic revision --autogenerate -m "mensagem"
docker compose exec backend python -m app.cli.import_items

# testes e lint
docker compose exec backend pytest -q -rs
docker compose exec backend ruff check .
docker compose exec frontend npm run test
docker compose exec frontend npm run typecheck
```

Atalhos equivalentes no `Makefile`.

Testes de integração (`backend/tests/integration/`) precisam de Postgres e usam o
banco `albion_test`. Sem banco eles **pulam** com a razão impressa — nunca passam
fingindo ter testado. Use `-rs` para ver os skips.

## Sobre a fonte de dados

Os preços vêm do Albion Online Data Project, coleta **comunitária**: o dado existe
porque algum jogador abriu aquele mercado no jogo com o client rodando.

Consequências que a UI precisa comunicar sempre:

- nenhuma cotação é garantida;
- mercado pouco visitado tem dado velho ou nenhum;
- `liquidity_status = UNKNOWN` é um estado legítimo, não um erro.

Formatos, armadilhas e o que foi verificado empiricamente: `docs/02-aodp.md`.
Duas que pegam todo mundo: o endpoint de preços chama o campo de `city` e o de
histórico chama de `location`; e o histórico devolve **média**, não mediana, então
um único preço manipulado contamina a janela inteira (visto na validação: 3.6k →
29.7k → 3.7k em dias consecutivos).

## Como trabalhar aqui

- **Uma fase por vez.** Terminar significa: testes verdes, lint limpo, comandos
  documentados no README. Não avance em silêncio.
- **Verifique antes de assumir.** Este projeto já teve dois palpites errados
  corrigidos por checagem: recurso bruto é `resources` e não `rawresources`; e
  `_LEVELN` no id de item às vezes é encantamento e às vezes faz parte do nome
  (`T1_FISHSAUCE_LEVEL1/2/3` são itens distintos).
- **Teste o comportamento, não a implementação.** Os testes bons deste repo
  descrevem uma armadilha real no nome: `test_sentinela_vira_none_e_nao_zero`,
  `test_janela_de_5_minutos_e_o_limite_que_manda`.
- **Injete relógio e espera** em qualquer coisa temporal, para que o teste
  verifique 5 minutos em milissegundos.
- **Commits em português, formato convencional**: `feat(collector): ...`,
  `fix(market): ...`, `docs: ...`, `chore: ...`.
- **Migrations geradas pelo autogenerate não são reformatadas na mão** — o lint
  já as ignora. O que importa nelas é o SQL.

## Armadilhas conhecidas

- `alembic/env.py` lê a URL de `app.core.config`, nunca de `alembic.ini` (que é
  versionado e não pode ter credencial).
- `is_tracked` em `items` é decisão operacional, não metadado do jogo. Reimportar
  o catálogo **não** sobrescreve, a menos que se passe `--apply-tracking`.
- Timestamps do AODP vêm sem fuso e são UTC. Deixar o driver adivinhar desloca o
  preço em horas.
- Nomes de local têm espaço: `Fort Sterling`, `Black Market`. A chave de lookup é
  a string exata da API, guardada em `locations.aodp_name`.
- Black Market não é cidade (`kind = 'black_market'`) e a semântica de ordens é
  invertida. Não use como perna de arbitragem antes de validar empiricamente.

## Próxima fase (6) — BLOQUEADA

Arbitragem precisa de imposto de venda e setup fee. Os parâmetros existem em
`config_parameters` com `value = NULL` e `source = 'UNKNOWN'`, e o levantamento
em `docs/04-taxas.md` encontrou **conflito entre as fontes** sobre qual
percentual é setup e qual é imposto de venda.

Não preencher por conta própria. O caminho é medir no jogo (roteiro no doc) e
gravar com `source` citando a medição.

Quando destravar, o motor deve:

1. Receber as taxas como **argumento obrigatório** das funções de
   `calculations/` — nunca ler configuração de dentro da fórmula.
2. Responder `UNKNOWN` para lucro, margem, ROI e score enquanto algum parâmetro
   necessário estiver `NULL`. Margem sem imposto é sempre otimista, e é melhor
   dizer "não sei" do que dizer "18,4%" quando o real é 11%.
3. Considerar transporte e liquidez antes de publicar uma oportunidade.

## Linguagem visual da tela de mercado

Linha densa, uma por item × cidade × qualidade, dividida em blocos rotulados
pelo que significam na prática e não pelo nome do campo na API:

| Bloco | Conteúdo |
|---|---|
| identidade | badge de tier/encanto, qualidade, chip da cidade na cor heráldica, nome visual e id técnico |
| comprando agora | `sell_min` e `sell_max` — o que você paga |
| vendendo agora | `buy_max` e `buy_min` — o que você recebe |
| referência | mediana de 30 dias, distância do preço atual, giro por dia e cobertura do histórico |

Três regras que essa tela materializa:

- **"venda mín" isolado não diz nada.** O rótulo é sempre acompanhado da
  consequência: "o que você paga", "o que você recebe".
- **Preço fresco em mercado pouco visitado é preço frágil.** Por isso frescor e
  cobertura aparecem juntos: `há 8 min` ao lado de `3/30d` é um alerta, não um
  elogio.
- **Liquidez desconhecida é estado de primeira classe.** Sem histórico
  suficiente, a barra some e o texto diz "liquidez desconhecida".

A cor das cidades vem da identidade que elas têm no jogo. Não é decoração: numa
tela densa o jogador reconhece "laranja = Bridgewatch" antes de ler o texto.

## Notas da fase 5

- **Mediana, não média.** O AODP já entrega média por bucket; média de médias
  contaminadas propaga outlier. As estatísticas do período usam mediana.
- **Outlier é marcado, nunca apagado.** Um pico pode ser evento real (patch,
  guerra, escassez). O ponto fica gravado, aparece no gráfico como círculo
  vazado, e sai das estatísticas.
- **MAD em vez de desvio padrão.** Desvio padrão é calculado a partir da média, e
  num conjunto com um valor oito vezes maior o próprio outlier infla o desvio a
  ponto de deixar de ser detectado.
- **Séries com menos de 5 pontos não são avaliadas.** Qualquer critério marcaria
  metade da amostra.
- **A escala do gráfico ignora os outliers.** Incluir o pico de 29.790 numa série
  de 3.700 achataria a variação real contra a base.
- **Liquidez sai de `item_count` do histórico.** É a única medida de volume que a
  fonte oferece. Buckets marcados como outlier ficam fora do cálculo: pico de
  preço manipulado costuma vir com volume igualmente irreal. Menos de 3 buckets
  na janela devolve UNKNOWN.

## Notas da fase 4

- Um lote que falha não derruba a varredura: o erro é contado, o run vira
  `partial` e a coleta segue. Perder 50 itens é melhor do que perder 300.
- `use_cache=False` na coleta. Cache serve para leitura da API, não para coletar
  o mesmo valor de novo.
- Linha sem nenhum preço não é gravada. "Ninguém abriu esse mercado" não é uma
  observação de preço e sujaria o cálculo de frescor.
- Ordenação por preço usa `NULLS LAST`: `NULL` significa "sem ordem", não "mais
  barato".
