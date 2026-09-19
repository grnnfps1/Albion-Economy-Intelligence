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
| 6 | Opportunity Engine + arbitragem | ✅ taxas configuráveis pelo usuário |
| 7 | Crafting | ✅ |
| 8 | Refino | ✅ |
| 9 | Focus | ✅ |
| 10 | Dashboard | ✅ |
| 11 | Onde comprar cada material (`sourcing_mode`) | ✅ |
| 12 | Agricultura e animais | ✅ |
| 13 | Black Market validado + risco de rota | ✅ |
| 14 | Matriz de retorno por cidade, atividade e Focus | ✅ |
| 15 | Taxa de estação derivada do valor do item | ✅ |
| 16 | Especialização: redução do custo de Focus | ✅ |
| 17 | Preço manual sobrescrevendo a cotação coletada | ✅ |
| 18 | Layout de planilha + exportação CSV | ✅ |
| 19 | Calculador de crafting, spec por item, lucro/dia | ✅ |
| 20 | Retorno vira fórmula `RRR = B/(1+B)` | ✅ |
| 21 | Taxas de mercado **medidas no jogo** | ✅ |
| 22 | Bônus diário entra em `B`; calculador em colunas | ✅ |
| 23 | Calculador escala pela quantidade; razões invariantes | ✅ |
| 24 | Linha sem número diz **por quê**; base unitária | ✅ |
| 25 | Abreviação de valor grande, com fronteira explícita | ✅ |
| 26 | Histórico coletado; estado vazio da taxa da estação | ✅ |
| 27 | Retorno e intervalo de preço **antes** do cálculo | ✅ |
| 28 | Uma barra de rolagem; ícone ancora a coluna | ✅ |
| 29 | Pílula espelha a resposta; painel por tela; desvio de sessão em dev | ✅ |
| 30 | Ordenação clicável no cabeçalho, resolvida no servidor | ✅ |
| 31 | Ordenação uniformizada; tabela deixa de encolher | ✅ |
| 32 | Focus fracionário derrubava /crafting e /focus | ✅ |

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
   cálculo como argumento. A da estação é derivada de `items.item_value`, que
   vem do dump — mas a prata por 100 de nutrição continua sendo do usuário.

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

12. **`_LEVELN` já mordeu quatro vezes. Pergunte sempre: isto muda com
    encantamento?**

    Sempre o mesmo erro de fundo — um campo que varia com encantamento tratado
    como se não variasse, ou um identificador que precisa do sufixo `@N` sendo
    usado sem ele:

    | # | Fase | Campo | O que aconteceu |
    |---|---|---|---|
    | 1 | 2 | o próprio `_LEVELN` | Às vezes é encantamento, às vezes faz parte do nome (`T1_FISHSAUCE_LEVEL1/2/3` são itens distintos). Resolvido consultando o dump, não a string. |
    | 2 | 7 | **nome do material** | O dump diz `T4_ROCK_LEVEL1`; o catálogo e o AODP dizem `T4_ROCK_LEVEL1@1`. Sem recompor, 12 mil materiais órfãos e custo de craft encantado baixo. |
    | 3 | 15 | `@itemvalue` | Peso e categoria são iguais entre base e encantado, então herdar a raiz sempre funcionou — mas o item value **quadruplica** no nível 2. Taxa de estação 16× menor no encantamento 4. |
    | 4 | 19 | **nome da saída** | Mesma recomposição da #2, do outro lado da receita. 80 recursos refinados encantados ficaram sem receita nenhuma, em silêncio. |

    O padrão que une as quatro: **o que é idêntico entre base e encantado
    esconde o que não é.** Peso, tier e categoria não variam, então o
    agrupamento por raiz parece seguro — até encontrar o campo que varia.

    Por isso, **todo campo novo lido do dump exige a pergunta antes de usar**:
    *isto muda com encantamento?* Se muda, a chave é a entrada literal
    (`T8_LEATHER_LEVEL2`), não a raiz. Se é identificador que vai ao mercado, o
    sufixo `@N` precisa ser recomposto — **nos dois lados**, material e saída.

    E o corolário que custou a #4: falha de casamento de nome **não pode ser
    silenciosa**. A receita era descartada sem log, sem contador, sem teste — e
    o importador de receitas não tinha teste nenhum até a fase 19.

13. **Resíduo de subtração não é uma grandeza.** Tirar o que se conhece de um
    total agregado e chamar o que sobra pelo nome da parcela que falta é
    inventar um número: o resíduo carrega tudo que não foi modelado **mais** o
    erro de tudo que foi modelado errado.

    Quando a conta não fecha, **a primeira hipótese é que a coluna certa está
    em outro lugar** — não que a fórmula está errada. Procurar a coluna é
    barato; refutar uma fórmula com fonte oficial deveria custar muito mais que
    três números reconstruídos de segunda mão.

    Isto não é teórico: a fase 15 declarou "a fórmula não reproduz o observado"
    com base num resíduo, e a fonte estava certa o tempo todo — a planilha tinha
    a taxa em **duas** colunas próprias, que confirmam a fórmula em 49 linhas.
    O relato está em `docs/04-taxas.md` §11, "O que eu errei".

14. **Campo que pode virar fracionário por construção nunca é `int`.**

    `focus_cost` era `int` e recebia `54 × 0,5^(FCE/10000) = 17,6908`. O
    Pydantic aceita `54.0` — float **sem** parte fracionária — num campo `int`,
    e recusa `17,6908`. Resultado: `/crafting` e `/focus` respondendo 500
    inteiras, com o frontend dizendo "a API não respondeu".

    **O que esconde é o caso padrão devolver valor redondo.** Sem
    especialização o multiplicador é `1,0` e o resultado sai inteiro; o tipo
    errado atravessou da fase 16 à 32 sem nenhum sintoma.

    Vale para tudo que passa por **multiplicador, taxa ou divisão**: custo com
    desconto, quantidade com retorno, focus com spec, qualquer média. A
    pergunta antes de escrever `int` é *existe entrada que torne isto
    fracionário?* — não *o valor que eu tenho na mão agora é inteiro?*

    O irmão do campo já dizia a verdade: `base_focus_cost`, o focus **antes**
    da redução, era `float | None` no mesmo `class`. Quando dois campos
    descrevem a mesma grandeza em momentos diferentes, o que passou pelo
    multiplicador é o que precisa de mais casas, não menos.

15. **Teste de serialização exercita o parâmetro opcional PREENCHIDO, não só
    ausente.**

    Todos os testes de API passavam `spec_levels=None`, e `None` percorre o
    caminho em que o multiplicador é `1,0`. A regra 14 esteve quebrada por
    dezesseis fases com a suíte inteira verde.

    Parâmetro opcional tem **dois** caminhos, e o interessante é quase sempre o
    preenchido: é ele que aciona a redução, o desvio de cidade, a sobrescrita.
    Testar só a ausência testa o caminho que já funcionava.

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
  catalog/           parser + importador do catálogo, receitas e agricultura
  collectors/aodp/   client do AODP
  calculations/      funções puras de taxa/lucro     (fase 6+)
  opportunities/     motor de score                  (fase 6+)
  services/sourcing.py  política de em qual cidade comprar cada material
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

O teste do collector também precisa de Redis, em `TEST_REDIS_URL` — **banco 15,
nunca o da aplicação**: o fixture roda `flushdb`. Sem a variável ele deriva a URL
de `REDIS_URL` trocando o número do banco, o que faz o mesmo comando funcionar
dentro e fora do compose (`localhost` fixo não funcionava dentro do container).

O schema de teste sai de `create_all()` e **não é migrado**: depois de acrescentar
coluna a uma tabela existente, rode `drop schema public cascade; create schema
public;` em `albion_test` antes da suíte, ou a coluna nova não existe lá.

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

## Acesso via Discord

Quem está no servidor configurado em `DISCORD_GUILD_ID` entra. A fonte da
verdade é o Discord: sair do servidor tira o acesso no próximo login, sem lista
paralela que alguém precise lembrar de atualizar.

- **O portão é o `middleware.ts`**, não cada página. Esquecer de proteger uma
  rota nova é o jeito mais comum de furar login; o middleware fecha por padrão.
- **Sem `SESSION_SECRET` e `DISCORD_CLIENT_ID`, a aplicação roda aberta.** É o
  modo de desenvolvimento local. Seguro porque um deploy sem esses valores nem
  chega a autenticar ninguém.
- **A sessão usa Web Crypto, não o módulo `crypto` do Node**, porque o
  middleware roda no runtime edge, onde o módulo de Node não existe.
- **O cookie é assinado, não criptografado.** Só guarda id, nome e avatar. Nada
  de `access_token`: quem roubasse o cookie poderia agir no Discord em nome do
  usuário.
- **`state` obrigatório no OAuth.** Sem ele, qualquer site forja um callback e
  loga a vítima numa conta que não é dela. Há verificação e o callback forjado
  cai em `/login?erro=estado`.
- **Expiração é checada na verificação**, não só no `max-age` do navegador: um
  cookie antigo continua assinado para sempre.

## Armadilhas conhecidas

- **Campo de lista em `Settings` precisa de `NoDecode`.** O pydantic-settings
  decodifica listas e dicts como JSON **antes** de qualquer `field_validator`
  rodar, e só quando o valor vem de variável de ambiente. `CORS_ORIGINS=http://x`
  derrubava a aplicação no startup. Pior: o teste passava, porque construir
  `Settings(cors_origins="...")` como argumento não passa pelo
  `EnvSettingsSource`. **Todo campo de lista/dict novo precisa de teste com
  `monkeypatch.setenv`**, não com argumento de construtor.

- `alembic/env.py` lê a URL de `app.core.config`, nunca de `alembic.ini` (que é
  versionado e não pode ter credencial).
- `is_tracked` em `items` é decisão operacional, não metadado do jogo. Reimportar
  o catálogo **não** sobrescreve, a menos que se passe `--apply-tracking`.
- Timestamps do AODP vêm sem fuso e são UTC. Deixar o driver adivinhar desloca o
  preço em horas.
- Nomes de local têm espaço: `Fort Sterling`, `Black Market`. A chave de lookup é
  a string exata da API, guardada em `locations.aodp_name`.
- Black Market não é cidade (`kind = 'black_market'`), mas a semântica de ordens
  **não** é invertida — isso foi suposição, e a validação de 16/09/2026 a
  desmentiu (`docs/02-aodp.md`). Ele preenche `buy_price_max` em 40/40
  equipamentos, com `sell_price_min >= buy_price_max` em 38/38. Entra como
  **destino de venda**; como origem de compra continua fora, porque comprar lá
  não foi medido. E ele não negocia recurso: 7 de 7 recursos vieram zerados.

## Taxas: configuração do usuário, não do servidor

O imposto de venda depende de a conta ter Premium. Um valor fixo de servidor
mostraria lucro errado para metade das pessoas. A precedência é:

```
parâmetro da requisição  →  config_parameters  →  UNKNOWN
```

**As taxas de mercado foram medidas no jogo** (fase 21, Fort Sterling,
19/09/2026): setup fee **2,5%** nas duas pernas, imposto **4%** com Premium e
**8%** sem. São os primeiros parâmetros do projeto com medição direta — todo o
resto que tem valor veio de comunidade, anúncio oficial ou planilha de
terceiro.

A precedência não mudou: parâmetro da requisição ainda vence a configuração,
porque quem tem Premium e quem não tem pagam impostos diferentes. O que mudou é
que o padrão do banco deixou de ser `NULL`. Qualquer parâmetro que continue
ausente segue respondendo `economics.known = false` com o motivo. **Nunca
calcular com taxa zero.**

A **taxa da estação** (`crafting.station_fee_per_100_nutrition`) é o único
parâmetro que também nasce vazio **na interface**, e não só no banco. A fórmula
que a consome está confirmada; o número é escolha do dono da estação e está
escrito na tela dela, dentro do jogo. Pré-preencher seria inventar número
(regra 2) e transformar a escolha de um jogador em padrão de produto (regra 5).

As funções de `calculations/fees.py` recebem `FeeProfile` como argumento
obrigatório. Nenhuma delas lê configuração.

## Notas da fase 32 — o spec derrubava duas telas inteiras

- **`CraftEconomicsOut.focus_cost` era `int` e o valor é fracionário.** Com
  especialização, `54 × 0,5^(16000/10000) = 17,6908`, e o Pydantic recusa float
  com parte fracionária num campo `int`. Resultado: **500** em `/crafting` e
  `/focus`, com o frontend dizendo "a API não respondeu".
- **O caso comum escondia o tipo errado — de novo.** O padrão de spec é zero, e
  zero devolve `54.0`, um float **sem** parte fracionária, que o Pydantic aceita
  num `int`. Todos os testes de API passavam `spec_levels=None`. O bug estava lá
  desde a fase 16 e só apareceu quando alguém informou uma especialização.
  É a regra 12 com outra roupa: lá era o encantamento que não mudava peso nem
  categoria; aqui é o spec zero que devolve um número redondo. Virou a **regra
  14**, e o que deixou passar virou a **regra 15**.
- **A pista estava na linha de baixo.** `base_focus_cost` — o focus **antes** da
  redução — já era `float | None`. O campo reduzido, que é o que de fato vira
  fracionário, ficou `int`. Os dois foram escritos no mesmo commit.
- **`farming.focus_cost: int` está certo e ficou.** Agricultura não aplica
  especialização: o valor vem do dump e é multiplicado por um inteiro de ciclos.
  Conferido antes de "consertar" por simetria.
- **"A API não respondeu" cobria três causas com ações opostas.** Container
  parado pede `docker compose ps`; tempo limite diz que a rota está lenta e que
  reiniciar não adianta; 500 diz que há exceção no log e a infraestrutura está
  boa. Este bug foi o exemplo: a tela mandava olhar a infraestrutura, que estava
  saudável. `ApiDown` agora nomeia a causa e diz o comando.
- **O motivo viaja por `cache()` do React, não por uma união de tipos.** As oito
  telas tratam ausência como `null`, e mudar o contrato obrigaria a reescrever o
  afunilamento de tipo em todas para ganhar uma frase. `cache()` é memoização
  **por requisição** no App Router: cada requisição tem a sua caixa, sem o
  vazamento entre usuários simultâneos que uma variável de módulo teria.

## Notas da fase 31 — ordenação uniforme, e a tabela que encolhia

- **`width: 100%` com `table-layout: fixed` encolhe em silêncio.** Virou regra
  na seção "Linguagem visual". O sintoma aparece longe da causa: quem vê um
  rótulo cortado procura a largura daquela coluna, e o problema está numa
  declaração que vale para a tabela inteira.
- **`/crafting` e `/focus` trocaram pílula por `SortHeader`.** Dois mecanismos
  para a mesma ação obrigam a aprender duas vezes, e o do cabeçalho mostra em
  **qual coluna** a ordem está aplicada, em vez de num rótulo separado da
  tabela. Cada tela manteve o seu padrão: prata/focus em `/crafting`, ganho
  realizável em `/focus`.
- **`/crafting` ordenava por ROI e não mostrava ROI.** Ele ganhou coluna na
  conversão: ordenar por um número que não se vê é pedir confiança sem dar como
  conferir.
- **Rótulo longo precisa de `numWide` quando a coluna ordena.** "lucro
  ajustado" e "ganho realizável" não cabem em 6,8rem com a seta, e rótulo
  truncado num cabeçalho clicável é pior que em outro lugar — ele é o alvo do
  clique. Medido antes de propagar, e foi o que o piloto existia para achar.
- **`/market` fica com a pílula, e a decisão está escrita no arquivo.** As
  colunas dela são blocos compostos (`sell_min` e `sell_max` juntos), e um
  cabeçalho que contém dois números não pode dizer por qual ordena. Separar os
  blocos resolveria a ambiguidade e mataria o que a tela faz de melhor: ver o
  spread de relance.
- **PENDENTE — `/refining` e `/arbitrage` não têm ordenação nenhuma.** Nem
  pílula, nem `sort_by` no backend: ordenam com ordem fixa no serviço.
  Convertê-las **não é trocar de componente** — é escrever a ordenação no
  backend (chave, direção e a regra de desconhecido-no-fim), e só depois o
  cabeçalho. Ficou fora desta leva de propósito.
- **O balão do material virou só a lista de cidades.** Saíram o id técnico, o
  "receita pede N", o "comprar N", o intervalo e a contagem de cidades. Os três
  do meio já estão na célula — repetir é a regra "nada duplicado"; o id e a
  contagem são metadado que não decide nada e empurrava para baixo as seis
  linhas que decidem. Fonte monoespaçada e `white-space: pre` porque as colunas
  são montadas com espaço: em proporcional, o espaço é mais estreito que o
  dígito e a coluna sai torta.

## Notas da fase 30 — ordenação por coluna

- **Tier é uma coluna ordenável, não um estado à parte.** Ela é o padrão da
  tela e o destino do terceiro clique, porque é ela que dá sentido ao formato:
  comparar T5.2 com T6.2 correndo o olho na vertical é o motivo de a tabela
  existir assim. Um padrão que só se recupera recarregando a página deixa de
  ser padrão.
- **Ordena pelo par `(tier, encantamento)`, nunca pelo rótulo.** `"T5.4" <
  "T6.0"` como texto funciona **por coincidência**, e quebra no dia em que
  existir um T10 — que como string viria antes de T2. Há teste com o nome dizendo
  isso.
- **Decrescente por tier não é simetria gratuita:** quem só produz T7 e T8 não
  quer rolar catorze linhas de tier baixo toda vez.
- **Linha sem cálculo vai para o fim — exceto por tier.** Lucro desconhecido
  não é lucro zero (regra 1) e não compete com número: num `desc` com `None`
  valendo zero, a bloqueada apareceria **acima** de toda linha que dá prejuízo,
  anunciada como melhor que um resultado real. Por tier é o contrário, e a
  diferença é de natureza: ali a posição é intrínseca ao item, e empurrar T8.4
  para o fim por falta de cotação quebraria a sequência que a ordenação existe
  para mostrar.
- **A separação conhecido/desconhecido entra antes do valor na chave, e o sinal
  entra no valor.** Se o `reverse` do `sorted` fizesse a inversão, ele
  inverteria também a separação e as bloqueadas subiriam ao topo no `asc`.
- **Quem ordena é o servidor.** Comparar lucro é aritmética de negócio, e o CI
  barra isso em `frontend/src`. O clique só reescreve a URL; não há `sort()`
  nenhum na tela.
- **A seta vem da resposta, não de estado local.** `data.params.sort_by` e
  `sort_dir` dizem o que o motor usou — mesmo princípio que consertou a pílula
  "sem focus" na fase 29: a tela não afirma o valor de um parâmetro cuja fonte
  é outra.
- **A seta só aparece na coluna ativa.** Uma seta cinza em toda coluna
  ordenável viraria ruído de doze setas e esconderia qual manda.
- **`SortHeader` nasce em `components/sheet/` mesmo tendo um só consumidor.**
  As telas de ranking ordenam por **pílula** na barra de filtros — outro
  mecanismo, outro lugar. Quando uma delas migrar, migra para cá, e as duas
  ordenações não vão parecer coisas diferentes.
- **Teste de contrato contra erro de digitação:** toda coluna de `SORTABLE`
  precisa existir em `CalcRowOut`. `getattr(linha, sort_by, None)` devolveria
  `None` em silêncio e a ordenação viraria "tudo desconhecido, mantém a ordem",
  sem erro nenhum.

## Notas da fase 29 — a tela não pode afirmar o que não é dela

- **A pílula "sem focus" mentia, e o cálculo estava certo.** O padrão do filtro
  era um literal (`padrao: "false"`) e a pílula acesa saía de
  `params.get(chave) ?? padrao`. Mas o valor enviado ao backend, sem parâmetro
  na URL, vem do **cookie de preferências**: com "Focus ligado: sim" salvo lá, a
  conta usava Focus, a decomposição somava os 59% corretamente, e a pílula dizia
  o contrário. O mesmo para o bônus do dia de 20%, que é valor gravado e não
  padrão indevido — `DEFAULTS.dailyProductionBonus` é zero.
- **A correção é de princípio: o filtro espelha a resposta.** `padrao` passou a
  vir de `data.material_return.use_focus` e `data.params.quantity` — o que o
  motor de fato usou. Uma tela não pode afirmar o valor de um parâmetro cuja
  fonte é outra; quando há duas fontes, a única afirmação honesta é a que veio
  de volta.
- **Parâmetro que aparece e não afeta nada ensina a ignorar o painel inteiro.**
  O painel de preferências passou a receber a lista de campos que a tela usa. No
  calculador saíram quatro, cada um conferido contra `build_calculator`: risco de
  rota (não é parâmetro da rota — refinar numa cidade não envolve viagem), Focus
  disponível (limita o ranking de `/focus`), Focus por dia (chega a `_linha` e
  morre lá) e Quantidade (virou pílula; o campo não é lido). O padrão continua
  "mostrar tudo": recortar é decisão explícita de quem conhece a tela, não efeito
  de esquecimento.
- **A corrente de flexbox da fase 28 estava errada, e errou em silêncio.** Ela
  dependia de cinco ancestrais com altura definida e `min-height: 0`; um elo
  frouxo não quebra — **encolhe**, e a tabela virou cinco linhas com espaço
  sobrando. Voltou a medição, agora com o que faltava na fase 26: somar os
  **irmãos seguintes** (o rodapé de "como ler"). Sem isso a tabela ia até o fim
  da janela, o rodapé transbordava e a página ganhava a segunda barra.
- **Rótulo que não cabe na coluna é pior que rótulo abreviado.** "custo de
  produção" em 6,8rem era cortado no meio da palavra pelo navegador, sem aviso.
  Virou "custo", com o nome inteiro no balão.
- **Desvio de sessão em desenvolvimento, com garantia de build.**
  `DEV_AUTH_BYPASS=1` só vale com `next dev`, porque a outra condição
  (`NODE_ENV === "development"`) vira literal no build e o bloco é **eliminado**
  do artefato. Conferido grepando o `.next`: zero ocorrências no `.js` de
  produção, e o portão intacto no mesmo arquivo. Não é "desligado em produção" —
  não foi compilado. Detalhe e a medição em `docs/06-seguranca.md`.
- **O desvio libera passagem, não forja identidade.** A sessão segue nula, que é
  o estado do modo aberto que já existia — assim ele não cria caminho de código
  exclusivo de desenvolvimento. E enquanto está ligado há uma tira âmbar
  dizendo que ninguém está autenticado: um app que **parece** logado e não está
  é o pior resultado possível de um desvio.

## Notas da fase 28 — a rolagem, o ícone e o que ainda mora nas preferências

- **Duas barras de rolagem vinham de duas coisas rolando.** A tabela tinha
  altura limitada e rolava; a página, por ter conteúdo abaixo dela, rolava
  também. Pior que a redundância: a de fora movia o cabeçalho que a de dentro
  acabara de prender.
- **Quem mede a altura agora é o layout, não o JavaScript.** A fase 26 media o
  topo da tabela e escrevia `--sheet-top`. Funcionava e era maquinário demais
  para uma conta que o flexbox faz sozinho: `PageShell` limita a coluna à
  janela, e a tabela é o único item que cresce. `SheetScroll` foi removido.
- **Abaixo de `md` nada disso vale, de propósito.** Numa tela estreita, prender
  a tabela deixaria a janela de leitura menor que a própria linha. Lá a página
  rola inteira, como sempre rolou, e o `flex: 1` não tem o que esticar.
- **O ícone vem antes do valor porque é a âncora da coluna.** O bloco estava
  alinhado à direita: o número ia para a borda oposta e o ícone ficava solto à
  esquerda, então de relance a coluna começava pelo número. Alinhar à esquerda
  cola os dois e devolve a ordem que o olho procura — é o mesmo arranjo do
  `MaterialCell` das telas de ranking.
- **Balão: a idade fica, a dedução sai.** `Lymhurst 100 (há 3 d, velha, fora do
  intervalo)` virou `Lymhurst 100 · há 3 d`. A idade decide e é decisão do
  projeto desde a fase 4; "velha" e "fora do intervalo" são dedutíveis dela e
  da cor, e repetir a dedução ao lado do dado gasta três palavras para não
  dizer nada novo. Marcas viraram sinal: `←` a usada, `✎` a manual.
- **O botão de preferências não ficou redundante — dezesseis campos vivem só
  lá.** Servidor, cidade de venda, Premium, imposto, setup fee, bônus do dia,
  Focus disponível, Focus por dia, os dois de risco de rota e os seis de
  especialização. O que ganhou atalho foram quatro: cidade de compra, Focus
  ligado, quantidade e taxa da estação. Ele passou a se chamar
  **"⚙ preferências"**, porque risco de rota e especialização nunca foram
  "taxas e focus".
- **Cidade é preferência; ilha é cenário da tela.** A distinção decide onde cada
  uma é guardada. A cidade vale para /market, arbitragem e refino, então o
  painel grava o **mesmo cookie** que o formulário — um lugar só, dois caminhos
  até ele. Guardá-la na URL faria a escolha sumir ao trocar de tela e deixaria
  o campo "Comprar em" mostrando outra coisa. Produzir na ilha é uma pergunta
  que só o calculador faz, fica na URL e é compartilhável pelo link.

## Notas da fase 27 — mostrar antes, não depois

- **A informação já existia; faltava a hora.** Retorno por cidade, componentes
  de `B`, melhor cidade e diferença estão no motor desde a fase 20 — e só eram
  contados **depois** do cálculo. Quem estava em Caerleon sem Focus via 27
  linhas vermelhas e nenhuma pista de que trocar de cidade resolveria. Nenhuma
  conta nova entrou nesta fase: só mudou quando ela aparece.
- **Três níveis, porque são três perguntas.** Componentes (`18% + 40% + 59% =
  117%`) respondem *de onde vem*; o resultado (`53,9%`) responde *o que entra na
  conta*; a comparação (`Martlock dá 36,7% para couro; aqui você está em 15,2%`)
  responde *o que estou perdendo*. Só o resultado seria correto e inacionável;
  só os componentes, aritmética sem conclusão.
- **A parcela que não se aplica fica na soma, apagada.** É o que o usuário
  poderia ter e não tem — some do total, não da tela. Escondê-la deixaria o
  número certo e a decisão invisível.
- **O rótulo do bônus nomeia a cidade que o dá, não a que está em uso.** "refino
  em Martlock 40% (não)" diz o que fazer; "refino em Caerleon 40% (não)" não diz
  nada.
- **O bônus depende da família, e a lista reage.** Martlock 36,7% para couro e
  15,2% para tábuas; Fort Sterling o inverso. Por isso a lista vem do backend
  por família: replicá-la no frontend violaria a regra 3 e divergiria da fórmula
  no primeiro ajuste — mesmo motivo pelo qual a matriz de oito células saiu de
  `config_parameters` na fase 20.
- **A ilha é o único caso em que o Focus não é melhoria marginal.** Sem a base
  de cidade, `B` é zero e **nada** volta; com Focus vai a 37,1%. Nas cidades o
  Focus soma; na ilha ele é a diferença entre haver retorno e não haver, e o
  painel diz isso só quando a ilha está selecionada.
- **O intervalo de preço por material responde "vale a viagem?".** A tela
  mostrava só o preço usado, e com isso não dava para saber se a escolha
  economizou muito ou foi indiferente. Agora: menor, maior e o percentual, com
  a lista de cidades no balão.
- **Uma cotação só não é intervalo de zero — é falta de alternativa.** Zero
  diria "todas as cidades cobram igual", que é afirmação sobre o mercado; falta
  de alternativa é afirmação sobre o que se sabe dele, e muda a confiança no
  número. A tela as escreve diferente, e há teste separando as duas (duas
  cidades com o mesmo preço **são** comparáveis, com espalhamento zero).
- **Só cotação fresca forma o intervalo, e a velha continua no balão.** Incluir
  a velha faria o "maior preço" ser sempre a cidade que ninguém visita. Mas ver
  que Thetford tem preço de três dias é informação, então ela aparece na lista,
  etiquetada.
- **Uma premissa de desempenho caiu, e foi medida antes de cair.** O modo
  CIDADE_UNICA consultava só a cidade base porque "não podia ficar mais caro em
  banco por um recurso que não usa". Agora ele usa. Medido: 14 ms para 50
  materiais em sete cidades, contra os ~2.100 ms da requisição inteira. O
  `choose()` continua restrito pelo modo: ganhou-se informação, não
  comportamento.

## Notas da fase 26 — o vazio precisa se explicar

- **`market_history` estava com zero linhas.** O coletor de histórico nunca
  havia rodado, e por isso `liquidity_status` era UNKNOWN em tudo. Uma passada
  (`python -m app.cli.collect_history --server west --days 30`) trouxe **59.394
  buckets** de 455 itens em 10 requisições, com 2.429 marcados como outlier e
  zero rejeitados. "escoa em" passou a responder em 27 de 27 linhas.
- **A decisão de a taxa da estação nascer UNKNOWN continua certa, e mesmo assim
  a tela estava errada.** A regra 2 diz para não inventar número; ela não diz
  para deixar o usuário adivinhando. Sem a taxa, as 27 linhas ficavam com traço
  em oito colunas, e **traço repetido não se lê como "falta um dado" — se lê
  como "quebrou"**.
- **A tira do topo não bastava, e a razão é de hierarquia.** Ela dizia "taxa da
  loja: desconhecida" em âmbar, correto e invisível: um rótulo de 10px entre
  outros cinco parâmetros compete com eles, enquanto o vazio da tabela ocupa a
  tela inteira. Quando o sintoma é grande e a explicação é pequena, o usuário
  acredita no sintoma.
- **O campo veio junto do aviso.** Mandar "informe nas preferências" cria um
  segundo passo — abrir o painel, achar o campo entre quinze, voltar. Para o
  único parâmetro que bloqueia a tela inteira, o input fica no próprio aviso.
  Grava a mesma preferência, no mesmo cookie: atalho para o mesmo lugar, não uma
  segunda fonte de verdade.
- **Com o painel no topo, o ponteiro por linha virou ruído.** "falta parâmetro"
  em vinte e três linhas é a mesma frase vinte e três vezes. O traço voltou
  nessas linhas — mas agora ele tem quem o explique logo acima. As linhas com
  falta de **cotação** mantêm o texto próprio, porque o painel não fala delas.
- **Bug que o histórico revelou: `days_to_sell` morava dentro do ramo
  `known`.** Escoamento sai do giro medido e da quantidade pedida — não depende
  do lucro, e portanto não depende da taxa da estação. Sumia justamente nas
  linhas em que o usuário mais queria alguma informação na tela. Há teste de
  integração exigindo `known is False` **e** `days_to_sell` preenchido.
- **"0,0 d" se lê como ausência.** Giro alto arredondado a uma casa vira zero, e
  zero numa coluna que também tem "sem dado" confunde duas coisas opostas. Passa
  a ser **"< 1 d"**: o mercado absorve no mesmo dia, o que é informação boa.

## Notas da fase 25 — a abreviação voltou, e só até onde deve

- **Isto reverte a fase 18 de propósito, e a razão precisa sobreviver.** A fase
  18 escreveu "número cheio, nunca abreviado" e estava certa **para os dados que
  existiam então**: valores unitários, de quatro a seis dígitos, onde abreviar
  economizava o que não precisava ser economizado.
- **O que mudou foi o dado, não o princípio.** O calculador mostra produções
  inteiras, e `133.086.292` tem nove dígitos. A regra antiga aplicada a esses
  números não entrega precisão — entrega coluna estourada e valor cortado pelo
  navegador, que é pior que arredondado de propósito, porque não avisa.
- **Por isso a reversão é parcial e tem fronteira escrita.** Abrevia-se o
  contexto (custo, receita, taxas, investimento); lucro e campo de preço
  editável continuam cheios; a exportação nunca abrevia. A tabela está na seção
  "Linguagem visual".
- **Campo editável não se abrevia porque o texto volta.** `4,5K` digitado de
  volta é 4.500 ou 4.532? Abreviar a saída de algo que também é entrada cria
  ambiguidade que nenhum arredondamento justifica.
- **O exato fica a um hover de distância**, no balão de toda célula abreviada —
  é o que torna a perda de precisão aceitável na coluna de contexto.
- **A exportação tem teste próprio contra isso.** Os dois formatadores vivem no
  mesmo módulo de apresentação, e reaproveitar o de tela no arquivo é o atalho
  errado mais fácil de tomar. `133,1M` numa planilha vira coluna de texto e some
  do somatório sem avisar.
- **O limiar de 10.000 tem teste nos dois lados.** `9.999` sai cheio, `10.000`
  sai `10,0K`. E há um teste que demonstra a perda: dois lucros diferentes viram
  o mesmo texto abreviado — que é exatamente por que o lucro não usa a função.

## Notas da fase 24 — o diagnóstico é o conteúdo da linha

- **Oito traços numa linha não informam nada, e o motivo já estava na
  resposta.** `reason` vinha preenchido desde a fase 19 e morava só no `title`
  do navegador, que ninguém descobre. O conserto não foi calcular mais coisa —
  foi mostrar o que já se sabia.
- **`compute_craft` dizia só o primeiro impedimento.** Era uma sequência de
  `return`: material sem cotação vencia, e a falta do preço de venda ficava
  invisível. T7.4 e T8.4 tinham **os dois**, e quem consertasse um descobriria o
  outro só na tentativa seguinte. Agora os impedimentos são colhidos todos antes
  de responder.
- **Falta de parâmetro e falta de cotação não são a mesma ausência.** Uma é
  global, vale para as 27 linhas e some quando o usuário preenche um campo; a
  outra é da linha e nenhum campo a resolve — ou o mercado ganha uma ordem, ou
  se compra em outra cidade. `missing` e `missing_data` ficaram separados, e a
  tela trata cada uma como o que ela é: a rara e útil vai por extenso, a
  repetida vira ponteiro para a tira do topo, que já a anuncia.
- **Nome visual e id técnico juntos no motivo.** "sem cotação de Pelego Grosso
  Prístino (T7_HIDE_LEVEL4@4)": o nome para quem lê a tela, o id para quem vai
  procurar no dump. Só o id era ilegível; só o nome deixava a linha sem rastro.
- **"escoa em" vazio não era bug: `market_history` está com zero linhas.** O
  coletor de histórico nunca rodou. A coluna dizia "—", que significava ao mesmo
  tempo sem histórico, giro zero e erro. Agora diz **"sem dado"**, e o balão
  explica que falta coletar. É a regra 1 na apresentação: ausência tem nome.
- **A base da tabela virou a unidade.** O padrão era 100, e quase toda coluna
  nascia com oito dígitos — as células brigavam entre si antes de qualquer
  questão de largura. Com base unitária e o filtro multiplicando, o mesmo
  layout respira, e quem quer a produção inteira ainda a tem a um campo de
  distância.

## Notas da fase 23 — o que escala e o que não escala

- **A divisão é extensivo × intensivo, e trocá-las é um bug silencioso.** Custo,
  taxa da estação, receita, lucro, focus e investimento dobram quando a
  quantidade dobra. Margem, ROI e prata por focus são razões entre dois
  extensivos: `crafts` se cancela, e elas têm de sair **idênticas** em 1 e em
  10.000. Uma margem que sobe com a quantidade não parece erro — parece ganho de
  escala, e é por isso que precisa de teste.
- **As razões saem dos valores por execução, não dos totais.** Em matemática
  exata dá o mesmo; em ponto flutuante não: `(a·N − b·N)/(c·N)` e `(a−b)/c`
  diferem no último bit, e perto de `x,xx5` o arredondamento a duas casas vira
  para lados diferentes. Na grade do teste, 44 combinações divergiam no último
  dígito.
- **`compute_trade` saiu do craft, e levou dois problemas junto.** Ele arredonda
  a taxa **total** a duas casas — meio centavo fixo que não escala — e foi
  escrito para arbitragem, cobrando setup fee nas duas pontas. O item craftado
  não tem ordem de compra: sai da estação. A taxa de venda agora é unitária e
  exata, e o `buy_price=1` sentinela com a subtração do "setup fantasma" sumiu.
- **`production_cost` virou campo de `CraftEconomics`.** O serviço o montava
  somando três valores **já arredondados**, o que fazia `lucro ÷ custo` variar
  com a quantidade. Quem precisa de uma razão precisa do denominador antes do
  arredondamento, não depois.
- **A taxa da estação é por execução — confirmado no código e travado em
  teste.** 500 crafts pagam 500 vezes, porque a nutrição é consumida por craft.
  Se fosse taxa fixa da sessão, o lucro por unidade melhoraria só por produzir
  em lote; há teste dizendo que não melhora.
- **O arredondamento da lista de compras já estava certo**, e agora está
  demonstrado: `⌈quantidade × receita × (1 − retorno)⌉`, teto uma vez só. Por
  unidade daria `⌈5 × 0,6329⌉ × 500 = 2.000` contra os 1.583 corretos — 417
  pelegos de compra inventada, 26% a mais. O teste guarda o número.
- **Não havia rodapé de "melhor linha × produção" para remover.** A única coisa
  ao pé da tabela era o parágrafo "como ler", e ele virou o que faltava: a
  declaração de o que escala e o que não escala.

## Notas da fase 22 — o bônus diário, e o calculador em colunas

- **O bônus diário é o quinto componente de `B`.** A fase 20 concluiu que ele
  "não entra por soma" porque somá-lo ao retorno errava de 3 a 8 pontos. A
  medida estava certa e a conclusão errada: ele soma em `B`, antes da conversão.
  Refino com bônus de cidade e 10% diário dá `0,68/1,68 = 40,48%`; somado ao
  `RRR` daria 46,71%. Os 6,2 pontos de diferença caem exatamente na faixa que a
  tentativa anterior observou.
- **Retorno não é grandeza aditiva; bônus é.** É a mesma família da regra 13
  (resíduo de subtração não é grandeza): antes de somar dois números, conferir
  se eles vivem no espaço onde a soma significa alguma coisa. Somar `0,152 +
  0,367` esperando `0,519` é o caso óbvio; somar o bônus do dia ao retorno é o
  mesmo erro com números que não denunciam.
- **Por que as tabelas publicadas não fechavam segue desconhecido — e não
  importa mais.** A fórmula é derivada da mecânica, não calibrada contra elas.
  Fica escrito em `docs/04-taxas.md` para ninguém reabrir o item achando que há
  dívida escondida.
- **Lista de 15 taxas da planilha: conferência, nunca origem.** Onze caem
  exatamente nas combinações previstas (erro ≤ 0,08 pp) e quatro não fecham
  (0,57 a 0,93 pp — sete a doze vezes pior). A separação é limpa, então os
  quatro ficam registrados como não explicados em vez de arredondados. E um
  deles, 31,00%, aparece **fora de ordem** na lista, o que sugere valor digitado
  à mão e enfraquece a fonte. Replicar a lista ao lado da fórmula garantiria
  divergência no primeiro ajuste — foi por isso que a matriz de oito células
  saiu de `config_parameters` na fase 20.
- **Primeira contagem minha estava errada, e a correção ficou no documento.**
  Apurei "treze fecham, dois não" antes de conferir contra todas as
  combinações; são onze e quatro. A conclusão não mudou, o peso da evidência sim.
- **Campo livre no lugar de select de três opções.** O bônus era um `select` de
  0/10/20%. Três valores inventados ao lado de uma fórmula dão ares de constante
  do jogo a um número sorteado. Virou campo em percentual, padrão vazio, com
  `assumes_no_daily_bonus` na resposta.
- **Célula composta não tem largura própria.** Os materiais do calculador
  moravam empilhados dentro da célula do item: o terceiro saía do alinhamento, o
  preço encostava na borda e o "comprar N" truncava. `table-layout: fixed` só
  governa colunas, então o conserto é **uma coluna por material**, como no resto
  do produto. Mesma razão tirou o "investe" de dentro da célula do lucro: dois
  números de oito dígitos não dividem uma coluna de 6,8rem.
- **A coluna de material do calculador é mais larga que a do ranking** (11,5rem
  contra 9,5rem) porque carrega um campo editável e a linha "comprar N". Largura
  por *tipo* de coluna continua valendo; o tipo é que é outro.
- **Variante sem cotação não custa zero.** `calculator_service` somava
  `m.gross_cost or 0`, e a variante incompleta ganhava a comparação de "mais
  barata" por não ter preço. Agora ela vai para o ramo incompleto e a resposta
  nomeia o material que falta. É a regra 1 aparecendo num lugar onde ninguém a
  procurava: um `or 0` dentro de um `sum`.

## Notas da fase 21 — as taxas de mercado foram medidas

- **Primeiro parâmetro do projeto com medição direta.** Até aqui todo número
  gravado vinha de comunidade (fase 14), de anúncio oficial (15) ou de
  conferência contra planilha de terceiro (19). Estes foram lidos na tela do
  jogo.
- **O imposto incide sobre o preço bruto, e a notificação prova.** `140.440 −
  5.618 = 134.822` bate exato. Sobre o líquido daria 4,167% e a subtração não
  fecharia.
- **A medição desempatou o conflito das fontes.** Elas concordavam nos números
  2,5% e 4%/8% e discordavam sobre **qual é qual**. Agora se sabe: 2,5% é
  setup, 4% é imposto. A confusão sobrevivia porque a soma é quase a mesma numa
  conta de ida e volta — e só se revela numa conta separada por perna.
- **Três fontes convergem nos 6,5%**: medição, planilha do Albion VIP (6,5000%
  exato em todas as linhas) e comunidade. É mais confiança do que qualquer uma
  sozinha daria.
- **4% e 8% têm procedências diferentes, e a tabela guarda isso.** O 4% tem
  notificação do jogo; o 8% veio de confirmação do usuário. Os dois são 2× um
  do outro, e é justamente por isso que a distinção precisa estar escrita: quem
  derivasse um do outro produziria o mesmo valor e nada denunciaria o chute. Há
  teste guardando.
- **Uma das quatro ordens de setup não fecha, e ficou registrada.** 1.284
  debitou 34 onde `⌈32,10⌉` daria 33. As outras três arredondam para cima
  exatamente. Não inventei regra para explicar: 2,5% fica pelo peso do resto, e
  o resíduo está em `docs/04-taxas.md`.
- **O teste de procedência mudou de forma, não de espírito.** Ele exigia que as
  taxas fossem `NULL`; agora exige valor **e** fonte. Foi ele que caiu quando as
  medições entraram, que é exatamente o trabalho dele.
- **Sobra o item 5:** se o setup fee varia com a duração da ordem. As quatro
  ordens medidas usaram a mesma duração, então não testam isso — e se variar, a
  estratégia PACIENTE do calculador está errada.

## Notas da fase 20 — o retorno virou fórmula

- **A matriz de valores fixos saiu; entraram os bônus e a conversão.**
  `RRR = B ÷ (1 + B)`, com base de cidade +18%, refino da cidade +40%, craft da
  cidade +15% e foco +59%. Guardar a tabela **e** a fórmula deixaria as duas
  divergirem no primeiro ajuste.
- **A contradição do item 6 era aparente.** +40% oficial e 36,7% medido não se
  contradiziam: `0,58/1,58 = 0,367`. `B` é o que a estação soma, `RRR` é a
  fração que volta. É por isso que o número oficial é redondo e o da comunidade
  tem decimal.
- **Os bônus somam antes da conversão.** Somar as taxas convertidas daria 0,954
  onde o certo é 0,539 — quase o dobro.
- **A fórmula corrigiu uma célula da fase 14.** Craft com bônus de cidade e foco
  era 0,477 tabelado e é 0,479 pela fórmula. Sete das oito células fecham abaixo
  de 0,0006; essa desviava 0,0022, dez vezes mais. O tabelado é que estava
  impreciso.
- **É o inverso do erro da fase 15**, e vale notar: lá eu descartei uma fórmula
  com fonte oficial por causa de números reconstruídos. Aqui a fórmula corrige
  um número tabelado — porque ela reproduz sete de oito, e nenhuma reconstrução
  reproduzia mais de uma. O peso da evidência é que decide, não a ordem em que
  ela chegou.
- **Ilha é local de produção, não de compra.** `kind = 'island'`, inativa para
  coleta e sem ordens de compra: ilha não tem mercado. Quem produz nela compra
  numa cidade e carrega, e a tela trata as duas coisas como separadas. Sem a
  base de cidade, o retorno é 0% sem Focus e 37,1% com.
- ~~**O bônus diário continua fora**~~ — resolvido na fase 22. A evidência
  estava certa (somá-lo ao `RRR` erra de 3 a 8 pontos) e a conclusão errada: ele
  entra em **`B`**, não no `RRR`. Ver as notas da fase 22.
- **O imposto não era bug.** Conferido: o backend escolhe
  `market.sales_tax_pct.premium` ou `.standard` pela flag, ambos `UNKNOWN`, e o
  formulário acopla o seletor de Premium a 4%/8%. Ponta a ponta dá 6,5% com
  Premium e 10,5% sem.
- **No calculador a densidade cai de propósito.** Ícones maiores no item e nos
  materiais, botão de copiar em cada material da lista de compras, e coluna de
  Focus junto das outras de custo. São 27 linhas de uma família, não 40 de um
  ranking: o calculador é para examinar, não para varrer.

## Notas da fase 19 — calculador, spec por item, lucro por dia

- **O calculador é outra rota, não uma reforma do ranking.** `/crafting`
  responde *onde gasto meu Focus hoje*; `/crafting/calculadora` responde *quanto
  rende esta família se eu mexer nos preços*. Fundir as duas daria uma tela que
  responde mal as duas.
- **27 linhas por família — menos pedra, que tem 7.** Confirmado no dump: T2 e
  T3 não têm variante encantada em nenhuma família, e `STONEBLOCK` não tem
  nenhuma variante encantada.
- **Recalcular "na hora" é ida e volta ao servidor, por causa da regra 3.**
  Editar grava um preço manual (fase 17) e `router.refresh()` devolve a linha
  recalculada. Um `useMemo` local seria mais rápido e colocaria aritmética de
  lucro no frontend, que o CI barra.
- **A taxa de retorno não é campo livre.** Vem da matriz da fase 14; o usuário
  escolhe cidade e Focus. Campo aberto convidaria a digitar errado um número
  que o sistema já sabe.
- **A taxa da estação é o único parâmetro que nasce vazio.** Contra a convenção
  de "preenchido com aviso", e de propósito: os dois candidatos eram 1.666 (que
  perdeu a base quando a reconstrução caiu) e 184 (escolha de estação de **um**
  jogador). Além disso é o número mais fácil da lista de obter — está escrito na
  tela da estação —, e o 1.666 enganava justamente onde se conferiria, porque
  reproduzia o T4 por circularidade. A tela cita 184 como ordem de grandeza,
  nunca como padrão. Detalhe em `docs/04-taxas.md` §11.
- **Uma coluna por material, com a cidade visível.** A planilha tem oito pares
  de coluna por cidade porque não tem política de sourcing; nós temos desde a
  fase 11. Oito cidades × sete materiais × 27 linhas seriam 1.512 células.
- **A receita não é repetida em texto.** As colunas de material já são a
  receita, e o badge do ícone é **quanto comprar** — não a quantidade da
  receita. É a diferença entre "a receita pede 5" e "compre 317".
- **Bug achado e corrigido: setup fee fantasma.** `compute_craft` passava
  `buy_price=1` como sentinela e `compute_trade` cobra setup das duas pontas
  (ele foi escrito para arbitragem). Isso somava 2,5 de prata em 100 unidades e
  fazia a taxa de venda não ser exatamente o percentual anunciado. Não mudava o
  lucro — só o número exibido —, mas num calculador isso corrói confiança.
  Agora dá **6,5000%** exato.
- **Lista de compras não é quantidade × receita.** O retorno volta para o
  inventário e reduz o consumo: `qtd × receita × (1 − retorno)`, arredondado
  **para cima**. E o retorno é promessa, não fato — só se realiza para quem
  refina em sequência. A tela diz isso em uma linha.
- **A lista segue a variante escolhida.** Não adianta o motor escolher a receita
  com token e a lista mandar comprar pela outra.
- **Duas margens, rotuladas.** A "Margem de Lucro" da planilha é lucro ÷ custo
  de produção — que é ROI. A nossa é sobre receita bruta. As duas aparecem,
  porque margem alta com ROI baixo é armadilha de capital parado.
- **`/refining` perdeu as colunas "cadeia" e "idade".** A cadeia virou o balão
  da coluna "produzir" — qualifica o número de que faz parte — e a idade virou
  a cor do rótulo. A idade **não saiu do produto**: isso desfaria a decisão da
  fase 4.

## Notas da fase 18 — layout de planilha e exportação

- **As telas densas viraram `<table>` com `table-layout: fixed`.** Não é
  cosmético: sem largura fixa o navegador dá às colunas de material toda a
  folga e abre um vão morto antes das colunas de decisão — que são o motivo de
  a tela existir. Com largura por **tipo** de coluna (`SHEET_WIDTHS`), "lucro"
  fica no mesmo lugar em /crafting e em /refining.
- **Uma coluna por grandeza, uma coluna por material.** Quem vem de planilha
  encontra o mesmo modelo mental, e comparar o preço do mesmo material entre
  duas linhas vira leitura vertical em vez de caça dentro de uma célula.
- **O nome do material vai em balão próprio, não em `title` nativo.** O do
  navegador demora quase um segundo e some ao mover o mouse; numa tabela em que
  se passa por dez materiais, ele aparece depois que o cursor já saiu. O
  `title` ficou onde o atraso não incomoda: botões e cabeçalhos.
- **Botão de copiar colado no preço e visível sempre.** Alvo que só aparece no
  hover não é descoberto. Copia o **nome** por padrão, porque é o que a busca
  do mercado no jogo entende; `alt+clique` copia o id técnico.
- **Sem nome em português, o botão desabilita** — e isso foi medido, não
  escolhido por gosto. Entre os 455 itens rastreados, 30 não têm nome em
  português e **os mesmos 30 também não têm em inglês** (templates de Liga de
  Cristal). Cair no inglês cobriria zero casos. Ver as notas do adendo abaixo.
- **Exportação em seis telas**, do recorte visível, com o filtro no nome do
  arquivo. CSV com `;` e BOM: vírgula abre tudo numa coluna só no Excel
  pt-BR, e sem BOM "Tábuas" vira "TÃ¡buas".
- **Decimal com vírgula e sem separador de milhar.** `1683277,5`, não
  `1.683.277,5`: o ponto de milhar depende de a planilha adivinhar a locale, e
  quando erra a coluna inteira vira texto e some do somatório. É o inverso da
  regra da tela, onde o número vai cheio — lá quem lê é uma pessoa, aqui é um
  parser.
- **Falhar calado é o pior resultado.** Clicar e nada acontecer faz a pessoa
  clicar de novo sem saber se o arquivo saiu. `download()` joga `ExportError` e
  o botão mostra a falha em âmbar.
- **A exportação tem teste de verdade**, com o arquivo gerado e lido de volta
  por um parser de CSV escrito no próprio teste — contagem de linhas, formato
  numérico e a fórmula `=IMAGE(...)` escapada. Exportação é das poucas coisas
  em que o bug só aparece depois que o usuário abre o arquivo.
- **Função não atravessa a fronteira servidor→cliente.** Passar
  `ExportColumn[]` (que tem `value: (row) => …`) para o botão derrubava a página
  em runtime, não no build. O servidor achata com `toExportSheet` e o cliente só
  monta o texto. Está comentado em `lib/export.ts` para não ser refeito.
- **`DenseRow` e `ColumnHeader` foram removidos**: ficaram sem uso depois da
  conversão, e componente morto num kit de UI é convite a duas linguagens
  visuais.
- **Falso positivo do CI de novo.** A regra "sem cálculo no frontend" casa
  `profit={…} … />` por causa da barra do JSX. Mesma classe do `d04364d`; a
  solução continua sendo quebrar as props em linhas.

## Notas do adendo da fase 18 — itens sem nome

A premissa do adendo não se confirmou, e os números importam:

- **Os 266 `items_without_metadata` têm todos nome em português.** A interseção
  com "sem PT-BR" é **zero**. São itens sem entrada em `items.json` (a raiz do
  dump), não itens sem nome — `formatted/items.json` traz o nome deles
  normalmente.
- **Nenhum dos 266 é material de receita.** Interseção zero com os 1.742
  materiais de receita do dump.
- **`T8_METALBAR` tem nome**: "Barra de Aço de Adamante". O exemplo do adendo
  não é um caso real.
- **Quem realmente não tem nome são 865 itens**, e entre os 455 rastreados são
  **30** — todos da subcategoria `tokens`, e todos **também sem nome em
  inglês**. São templates de Liga de Cristal e um cristal de arena: não são
  itens de mercado.

Por isso o botão desabilita em vez de cair no inglês: o fallback foi medido e
cobre zero casos. Há ainda 44 materiais de receita sem PT-BR, todos fichas de
masmorra que também não têm EN — e nenhum deles é rastreado.

## Notas da fase 17 — preço manual

- **Quem está com o jogo aberto sabe mais que a coleta.** `manual_prices` deixa
  o usuário informar o preço, e onde houver preço manual ele vence o coletado.
- **Preço manual também envelhece, e é isso que o separa de uma sobrescrita
  permanente.** Passado o limite de frescor ele deixa de valer e o coletado
  volta. Um número digitado há três dias é pior que uma cotação de três dias:
  parece autoridade.
- **Expirado é dito, não ignorado.** A linha carrega `manual_expired` e a tela
  mostra em âmbar. Ignorar em silêncio faria o usuário achar que o preço dele
  continua valendo.
- **`kind` é nomeado pela consequência.** `COMPRA` sobrescreve
  `sell_price_min` (o que você paga) e `VENDA` sobrescreve `buy_price_max` (o
  que você recebe). É a regra 7 no lugar em que ela mais morde: chamar os dois
  de "preço" inverteria o sinal do lucro na metade dos casos.
- **A idade exibida é a de quando foi informado**, não a da cotação que ele
  substituiu. Herdar a idade do coletado faria um preço fresco parecer velho.
- **Reinformar renova a idade**, de propósito: quem reinforma acabou de olhar o
  mercado.
- **O coletado aparece riscado ao lado do manual.** Ver os dois é o que permite
  perceber um zero a mais — sem isso, um erro de digitação vira "oportunidade".
- **`user_id` é o `discord_id` da sessão.** Não há tabela de contas; a fonte da
  verdade do acesso já é o Discord. Quando contas existirem, vira FK sem mudar
  a semântica.
- **O backend não valida sessão: o Next manda `X-User-Id`.** É decisão de
  confiança, não esquecimento — o FastAPI não é exposto ao browser (regra 4).
  Está escrito em `api/deps.py` para o dia em que deixar de ser verdade.
- **Sem sessão, tudo se comporta como antes.** O overlay fica vazio; é o modo
  de desenvolvimento local, onde não há login.
- **Bug pego em teste:** `returning()` num UPSERT devolve o objeto do identity
  map, não o do banco. Reinformar devolvia o preço **antigo** com o banco já
  atualizado. `populate_existing=True` resolve.

## Notas da fase 16 — especialização

- **O custo em Focus do dump é o custo de quem nunca especializou nada.** A
  fórmula é `focus_base × 0,5 ^ (eficiência ÷ 10.000)`, com eficiência vindo de
  `nível_spec × 250 + (mastery + mastery2) × 30`. Um refino T4 custa 54 sem spec
  e 3 com tudo maximizado.
- **A tabela por tipo de peça não é custo base, é pontos por nível.** MAIN 250,
  BAG 310, CAPE 370, OFF secundário 90 — o padrão é `250 + irmãos do nó × 30`.
  O custo base vem do dump, item a item.
- **A tabela de custo base não virou código, de propósito.** O dump já a traz em
  `@craftingfocus` e os números batem valor por valor com a pesquisa de
  `docs/05-custo-de-focus.md`, diagonal inclusive (`T5.0 = T4.1 = 94`).
  Transcrever criaria uma segunda cópia para sincronizar a cada patch.
- **"Pedra é exceção" não tem consumidor.** `STONEBLOCK` tem zero variantes
  encantadas no dump, contra 20 em cada uma das outras quatro famílias. Bloco de
  pedra não é encantado; pedra bruta é. O aviso do doc ficou registrado, sem
  código.
- **Spec ausente é zero, e isso diverge das taxas de propósito.** É o precedente
  do risco de rota, não o das taxas: zero significa "não estou modelando
  especialização", o custo sai idêntico ao do dump e a resposta carrega
  `assumes_zero_spec`. O problema nunca foi o zero — foi o silêncio.
- **Por família, não por item.** Cinco números (couro, tecido, tábuas, barras,
  blocos) em vez das centenas que a planilha pede. Craft de equipamento ainda
  calcula com spec 0, que superestima o Focus — o lado conservador.
- **A redução entra no `RecipeSpec`, não em `chain.py`.** A recursão segue sem
  saber que especialização existe; quem aplica é o serviço, porque é preferência
  do usuário.

## Notas da fase 15 — taxa de estação

- **A taxa deixou de ser um número e virou uma derivação.** O jogo cobra por
  nutrição consumida, e a nutrição é `item_value × 0,1125` — fórmula anunciada
  pela própria Sandbox, não engenharia reversa. O usuário informa a prata por
  100 de nutrição, que é o número que ele lê na tela da estação.
- **Um valor fixo errava por duas ordens de grandeza.** `@itemvalue` dobra a
  cada tier e a cada encantamento: 4 no `T2_LEATHER`, 256 no T8, 4.096 no T8
  encantado 4. Os 100 fixos de antes eram razoáveis no T4 e ridículos nas duas
  pontas.
- **Cada elo da cadeia paga a taxa do que ele próprio produz.** `chain.py`
  recebe `station_fee_of` como função por item, não um número. Cobrar a taxa do
  T8 nos seis elos abaixo inflaria o custo; cobrar a do T2 em todos o
  esvaziaria.
- **A fórmula está CONFIRMADA — e a conclusão anterior desta nota estava
  errada.** Durante a fase 15 escrevi aqui que a reconstrução "não fechou". Ela
  não fechava porque eu reconstruí a taxa como **resíduo de subtração** de uma
  coluna agregada, sem verificar que a planilha tinha coluna própria. Tinha
  duas: `BD_Itens_Craft.Taxa Loja` (23/24 linhas dão `item_value × 0,1125 ÷
  100`) e `Crafters.Taxa da Loja` (26/27 linhas implicam F = 184, contra os 184
  que a própria planilha declara). Virou a **regra 13**.
- **Os três resíduos (5,17 / 29,98 / 2.496,79) não são a taxa de estação.** O
  teste que trava a aritmética da acumulação em cadeia continua válido como
  aritmética; a premissa é que estava errada. Recuperar os quatro tiers que
  faltavam deixou de importar.
- **O padrão pré-preenchido perdeu a base.** Os 1.666 prata por 100 de nutrição
  saíram da mediana das taxas implicadas por aqueles resíduos. O número segue
  em uso e a decisão sobre trocá-lo está aberta em `docs/04-taxas.md` §11.
- **Bug corrigido de carona:** `resolve_base_name` prefere a raiz sem `_LEVELN`,
  o que é certo para peso e categoria (idênticos) e errado para `@itemvalue`
  (256 contra 1.024). Todo item encantado estava herdando a taxa da base — 16×
  menor no encantamento 4. É a armadilha da fase 7 em outro campo.
- **Item sem `@itemvalue` é UNKNOWN, não grátis.** São 97 dos 455 rastreados:
  animais de pasto e ferramentas, que não passam por estação.

## Notas da fase 14 — matriz de retorno

- **O retorno deixou de ser um número e virou uma matriz** de (atividade ×
  cidade × Focus). O motivo é que a cidade pesa mais que o Focus em refino:
  0,152 → 0,367 só mudando de cidade. Com um valor único, essa decisão era
  invisível na tela.
- **Refino e craft têm bônus em eixos diferentes.** Refino segue o recurso (que
  segue o bioma da cidade); craft segue a família do item. Conferido: em 9 de 9
  peças de armadura a cidade que refina o material não é a que dá bônus para
  craftá-la. Não é inconsistência — é o que obriga o material a viajar.
- **A precedência inverteu em relação às taxas.** Nas taxas de mercado o valor
  do usuário é primário. Aqui a matriz é primária e a preferência é sobrescrita
  opcional, porque a matriz depende de (cidade, atividade, Focus) — coisas que
  o sistema sabe — e o usuário só precisa intervir quando a situação dele é
  atípica.
- **Número com valor exige procedência.** O teste que travava chute foi
  dividido, não afrouxado: imposto e setup fee seguiam NULL/UNKNOWN até a fase
  21 medi-los; a matriz
  exige valor na faixa, `source` diferente de UNKNOWN, data de consulta e a
  ressalva do que não foi auditado.
- **40% oficial e 36,7% medido não se contradizem.** Um é o bônus bruto da
  estação, o outro é o efeito realizado depois do sorteio por unidade. É por
  isso que o número da comunidade tem decimal. Detalhe em `docs/04-taxas.md`.
- **Prefixo, não substring, no mapeamento de família.** `2H_BOW` pega
  `2H_BOW_AVALON` e não pega `2H_CROSSBOW`, que é de outra cidade.
- **Bug corrigido de carona:** o refino lia `crafting.return_rate.base`. Enquanto
  as duas chaves eram NULL ninguém via; com a matriz preenchida, o refino usaria
  a taxa do craft.

## Notas da fase 13 — Black Market e risco de rota

- **A suposição estava errada, e só a consulta real mostrou.** Estava escrito
  aqui que a semântica de ordens do Black Market era invertida. Não é:
  `sell_price_min >= buy_price_max` em 38 de 38 linhas. O que ele tem de
  particular é encher `buy_price_max` **sempre** (40/40, contra 4/40 em
  Caerleon), porque as ordens de compra são de NPC. Número e amostra em
  `docs/02-aodp.md`.
- **Ele não negocia recurso.** 7 de 7 recursos consultados vieram com os quatro
  campos zerados. Não virou regra de negócio: é ausência de dado, e o cálculo
  responde `UNKNOWN` como sempre.
- **Destino sim, origem não.** Vender no Black Market foi medido; comprar lá
  não. Perna não medida não entra, mesmo quando o preço parece convidativo — há
  teste que falha se ele voltar a aparecer como origem.
- **Perder a carga não é ganhar zero.** A conta é
  `lucro × (1 − p) − investimento × p`. O segundo termo é o que quase toda
  calculadora esquece, e sem ele uma rota com 20% de perda parece render 80% do
  lucro quando na verdade também queima 20% do capital. Há teste comparando as
  duas contas lado a lado.
- **Risco tem padrão zero, e isso é diferente das taxas de propósito.** Taxa
  ausente vira `UNKNOWN` porque calcular sem imposto inventa lucro. Risco
  ausente vira zero porque significa "não estou modelando perda", e o ajustado
  sai idêntico ao bruto, à vista. Travar a tela por um número que só o usuário
  tem seria esconder o produto.
- **A zona é classificada pelas pontas, não pelo caminho.** O caminho é escolha
  do jogador; o que o dado tem são os dois mercados. Cidade real ↔ cidade real é
  azul; qualquer ponta em Caerleon ou no Black Market é vermelha/preta.
  `transport_routes.is_manual` existe para o caso em que a regra genérica erra —
  Brecilien é o exemplo conhecido, `royal_city` no cadastro mas só alcançável
  por portal das Brumas.
- **Os dois números sempre juntos.** Só o bruto esconde o risco; só o ajustado
  esconde de onde veio o desconto. Quando o risco é zero, aparece **um** número
  — repetir o mesmo valor duas vezes faria parecer que há diferença onde não há.
- **`risk` e `distance` do score saíram do papel.** Estavam em
  `config_parameters` desde a fase 0 sem fonte. Agora `risk` vem da preferência
  do usuário e `distance` vem da zona da rota. E o `profit` que alimenta o score
  passou a ser o **ajustado**: ranquear pelo bruto colocaria a rota de zona
  vermelha no topo justamente por ela pagar o prêmio do risco.

## Notas da fase 12 — agricultura e animais

- **O tempo é o ponto.** Um ciclo de fazenda leva 22 horas
  (`activefarmcyclelengthseconds` = 79.200) e um filhote de montaria T8 leva
  quase um mês. "Lucro por ciclo" ao lado de "lucro por craft" não compara nada:
  tudo sai em **prata por dia** e **prata por Focus**, e ordenar por ciclo
  premiaria o que é lento. Há teste demonstrando.
- **Duas fontes, não uma.** `farmableitem` diz o tempo, o Focus e a ração;
  `harvest.@lootlist` é só o *nome* da lista, e o que a colheita entrega mora em
  `loot.json`. Sem a segunda fonte não se sabe nem qual item sai nem quantos.
- **Nem tudo que cai é o motivo de plantar.** `T1_CARROT_LOOT` traz a cenoura a
  100% **e uma minhoca a 10%**. Tratar as duas como saída principal fez todo
  cultivo virar UNKNOWN na primeira rodada com preço real, porque ninguém cota
  minhoca. Chance 1.0 é o que separa as duas.
- **Quantidade é faixa.** O dump diz `3-6`, não `4`. A faixa fica nas duas
  colunas do banco e o cálculo usa a média — achatar na importação apagaria a
  incerteza antes de alguém poder vê-la.
- **Criação é cadeia**, e por isso reaproveita a política de compra do refino: a
  ração sai da fazenda, e a quantidade é `grow_seconds ÷ @secondspernutrition`
  convertida pelo `@nutrition` do alimento mais barato da categoria aceita.
- **A semente que volta não paga imposto de venda.** Ela é replantada, não
  vendida; cobrar imposto ali inventaria uma taxa que ninguém paga.
- **O que foi interpretado vai etiquetado.** `@activefarmmaxcycles` e
  `@activefarmbonus` não são inequívocos, e a resposta carrega
  `params.assumptions` dizendo isso. A lista de medição está em
  `docs/04-taxas.md`, itens 7 a 10. Um número plausível ao lado de um medido,
  sem etiqueta, vira medido.
- **Adulto que não produz nada não vira plano.** Ele é saída de uma criação, não
  uma decisão que alguém toma.

## Notas da fase 11 — onde comprar cada material

- **`sourcing_mode` é política de serviço, não fórmula.** Vive em
  `services/sourcing.py`; `calculations/` continua recebendo só preço. Três
  valores: `CIDADE_UNICA` (padrão e comportamento histórico), `MAIS_BARATO` e
  `COMPARAR`.
- **MAIS_BARATO nunca pode sair mais caro.** Se a única cotação fresca de fora
  está acima da cotação da cidade base — mesmo velha —, a base continua sendo a
  resposta. Sem essa trava, "mais barato" mandaria o usuário viajar para pagar
  mais.
- **Preço velho não entra na escolha.** Acima do limite de frescor, a ordem que
  justificava o desvio provavelmente já foi consumida. Ele ainda serve de
  fallback na cidade base, mas nunca ganha uma comparação.
- **Empate fica na cidade base.** Uma segunda cidade só se paga quando economiza;
  empate com viagem é prejuízo.
- **Economia sem número de cidades engana.** A resposta traz `cities_involved`
  junto de `savings`, e a tela avisa a partir da terceira cidade: 3% espalhados
  por quatro mercados custam quatro viagens.

## Backlog

- **`/refining` e `/arbitrage` sem ordenação.** As outras telas densas ordenam
  por cabeçalho clicável desde a fase 31; estas duas não ordenam de jeito
  nenhum — o serviço devolve ordem fixa e o backend não aceita `sort_by`. Exige
  ordenação **no backend** (chave, direção e desconhecido-no-fim), não só o
  componente de cabeçalho.

- **Hideout em zona preta chega a 58–60% de retorno com Focus.** Fora de escopo:
  a plataforma modela as cidades reais, onde está a esmagadora maioria dos
  jogadores. Registrado para não se perder.
- **Mapeamento de família de craft incompleto.** "Cajados de quartzo" e as linhas
  HALBERD, SCYTHE, GLAIVE, CLAWPAIR, FLAIL, KNUCKLES, SHAPESHIFTER e de bastão
  ficaram sem confirmação e caem no retorno sem bônus. Lista em
  `crafting.city_bonus_unmapped`.

## O plano original terminou

As dez fases do plano original estão implementadas, e mais duas vieram depois. O que vem agora não está planejado em detalhe;
é o que o documento original listava como "futuro". Em ordem de valor:

1. **Medir as taxas no jogo** (`docs/04-taxas.md`). Não bloqueia mais nada, mas
   define o padrão pré-preenchido. Treze medições: as seis de mercado e craft,
   as quatro que a agricultura trouxe (ciclos de Focus da criação, o que
   `@activefarmbonus` multiplica, o bônus de comida favorita e o preço fixo do
   comerciante de fazenda) e as três da taxa de estação.

   **A número 11 — taxa da estação — é a prioridade.** É a única da lista em
   que a fórmula tem fonte **oficial da Sandbox** e mesmo assim **não reproduz
   os valores observados** na planilha do Albion VIP: dos sete tiers prometidos
   só três chegaram, e os três implicam três taxas diferentes (1.148,9 /
   1.665,6 / 8.669,4). Também é a mais barata de resolver — craftar um T4 e um
   T8 na mesma estação e anotar os dois débitos decide, porque a fórmula é
   determinística e não exige amostragem.
2. **Contas e preferências.** Hoje os parâmetros do usuário vivem na URL. Com
   login, viram preferência salva — o cálculo não muda, só a origem do valor.
3. **Watchlist e alertas.** A arquitetura já está preparada; falta a tabela e o
   worker que avalia condições.
4. **Portfólio.** Registro de compras e vendas reais, para comparar o lucro
   previsto com o realizado. É o que fecharia o ciclo do produto.

Nada disso exige refazer o que existe.

## Parâmetros de crafting: entrada do usuário

Três parâmetros, pelo mesmo motivo das taxas de mercado — nenhum é fato fixo:

| Parâmetro | Por que varia |
|---|---|
| taxa de retorno de material | Focus, especialização da estação, bônus da cidade |
| taxa da estação | definida pelo dono, muda por cidade e por hora |
| imposto de venda | muda com Premium |

`profit_per_focus` é a ordenação principal: Focus é o recurso escasso, não a
prata. Lucro absoluto alto com Focus alto pode ser pior negócio — há teste
cobrindo exatamente isso. E prata/focus é **intensivo**: não muda quando se
aumenta o número de execuções, ao contrário do lucro absoluto.

## Linguagem visual

Desde a fase 18 as telas densas são **tabela** (`components/sheet/`), com
`table-layout: fixed` e largura por tipo de coluna. Uma coluna por grandeza,
uma coluna por material, zebra fraca e filtros em caixa alta. O que segue vale
dentro dessa tabela.

Linha densa, 40 por tela, com **cor carregando informação e nunca decoração**:

| Elemento | O que comunica |
|---|---|
| faixa à esquerda | tier, nas cores do jogo (T4 azul … T8 branco) |
| fundo tingido | verde = lucro, vermelho = prejuízo |
| moldura do ícone | tier de novo, para o olho separar antes de ler |
| ponto na cidade | cor heráldica oficial, sempre **acompanhada do nome** |
| pílula verde/vermelha | margem percentual, ao lado do lucro |
| âmbar | atenção: dado velho, parâmetro não verificado |

Regras que a tela materializa:

- **Rótulo diz a consequência, não o nome do campo.** "você gasta (materiais +
  taxas)" e "você recebe (após imposto)", nunca "custo" e "mercado" — rótulo
  vago esconde taxa.
- **Hierarquia por tamanho.** Lucro é o maior número da linha; custo e receita
  encolhem. Tudo com o mesmo peso visual é o mesmo que nada ter peso.
- **Tabela densa usa `width: max-content; min-width: 100%`.** Nunca
  `width: 100%`. Com `table-layout: fixed`, quando a soma do `colgroup` passa
  da largura usada, o navegador **não deixa a tabela transbordar — ele encolhe
  todas as colunas proporcionalmente**. O defeito é traiçoeiro porque nada
  some: tudo fica um pouco mais estreito, e só o conteúdo mais largo denuncia,
  longe da causa. Era isto por trás de "custo de produç" e do lucro de nove
  dígitos virando "+1.", e a barra de rolagem horizontal existia sem rolar
  nada, porque não havia transbordo.

- **Número cheio onde ele decide; abreviado onde ele situa.** A regra da fase
  18 era "cheio, nunca abreviado" e a fase 25 a reverteu **parcialmente** —
  leia a nota da fase 25 antes de reverter de novo. A fronteira:

  | Onde | Formato | Por quê |
  |---|---|---|
  | lucro | cheio | é o número que decide; `133.086.292` e `...291` são coisas diferentes ao conferir |
  | campo de preço editável | cheio | abreviar o que se digita cria ambiguidade na volta |
  | custo, receita, taxas, investimento | abreviado acima de 10.000 | é contexto, e em produção inteira tem nove dígitos |
  | exportação | **sempre cheio** | planilha soma número; `133,1M` é texto e some do somatório |

  Abreviação é `K`/`M`/`B`, vírgula decimal, uma casa: `133,1M`, `12,5K`,
  `1,2B`. **Abaixo de 10.000 não se abrevia** — `9,9K` é menos legível que
  `9.870` e ainda perde precisão. O valor exato vai no balão de toda célula
  abreviada.
- **Nome visual manda, id técnico no tooltip.**
- **Nada duplicado.** O badge do ícone é a quantidade; o texto é o preço
  unitário. Repetir a quantidade nos dois gasta espaço e confunde.

**Preferências ficam num cookie**, não na URL, e num formulário só
(`PreferencesForm`), recolhido por padrão e **já preenchido**. Antes cada tela
pedia os mesmos sete campos — era levar "não inventar número" longe demais. A
regra é não inventar **em silêncio**: o padrão vem preenchido com um aviso de
que não foi verificado no jogo.

`preferences.ts` é server-only e `preferences-shared.ts` tem os tipos. Misturar
os dois arrasta `next/headers` para o bundle do cliente e o build falha.

## Linguagem visual da tela de mercado (histórico)

Linha densa, uma por item × cidade × qualidade, dividida em blocos rotulados
pelo que significam na prática e não pelo nome do campo na API:

| Bloco | Conteúdo |
|---|---|
| identidade | ícone do item, badge de tier/encanto, qualidade, chip da cidade na cor heráldica, nome visual e id técnico |
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
tela densa o jogador reconhece "laranja = Bridgewatch" antes de ler o texto. Vale
o mesmo para a moldura do ícone, colorida por tier.

**Ícones** vêm do render oficial (`render.albiononline.com/v1/item/{id}.png`). A
URL é **derivada do `unique_name`, nunca armazenada** — o sufixo `@N` do
encantamento já vai no próprio id e o serviço entende. Guardar 12 mil URLs em
`items.icon_url` criaria uma cópia para migrar toda vez que o host mudar. As
imagens vão direto do CDN da Sandbox para o browser: proxiá-las pelo nosso
backend gastaria banda e latência sem benefício, e por isso também não se usa
`next/image` aqui.

## Notas da fase 10

- **O estado do pipeline vem antes dos números.** Se a coleta parou, todos os
  cards estão olhando um retrato antigo. A tira no topo mostra idade da última
  coleta e a fração de preços desatualizados, e muda de cor quando não está
  fresca.
- **Card indisponível continua na tela**, com o motivo. Sumir deixaria um buraco
  sem explicação, e o usuário não saberia que existe uma seção ali.
- **Top Oportunidades só traz arbitragem.** É a única categoria com score
  comparável hoje. Misturar categorias sem métrica comum produziria um ranking
  que não significa nada — melhor mostrar menos e verdadeiro. Quando craft e
  refino ganharem score, entram.
- **A home virou o painel; o estado do pipeline foi para `/status`.** Continua
  linkado da tira do topo.

- **Taxa não é ganho.** Prata/Focus responde "quanto rende cada ponto"; o que se
  leva para casa é limitado pelo Focus disponível **e** pelo que o mercado
  absorve. O ranking cruza os dois e devolve o ganho realizável no horizonte.
- **O limitador é informação de primeira classe.** Saber que uma operação está
  travada pelo mercado, e não pelo Focus, muda a decisão: adianta produzir mais
  ou adianta procurar outro item?
- **Ordenar só por taxa inverte o ranking.** Há teste demonstrando: item com
  taxa maior e giro de 1/dia rende menos que item com taxa menor e giro de
  800/dia. É a razão de o ranking existir.
- **Item que aparece por craft e por refino fica uma vez**, com a melhor rota
  marcada. Duas linhas para a mesma decisão é ruído.
- **Sem orçamento de Focus informado, o único teto é o mercado** — e a tela diz
  isso, em vez de fingir que a taxa basta.

## Notas da fase 8

- **A cadeia muda a pergunta.** Não é "vale refinar T5?" e sim "onde na cadeia
  T2→T8 está o gargalo". `calculations/chain.py` resolve o custo recursivamente.
- **Três formas de custear o insumo, e as três estão certas** — para pessoas
  diferentes. Quem compra tudo pronto usa `MERCADO`; quem já tem a cadeia montada
  usa `PRODUZIR`; `MAIS_BARATO` decide elo a elo. A resposta traz sempre as duas
  alternativas puras, para a comparação ficar explícita em vez de escondida numa
  escolha do motor.
- **Cada elo paga a taxa da estação, não só o último.** Em refino isso pesa muito
  mais que em craft avulso, e é o erro mais fácil de cometer.
- **Recursão tem limite de profundidade e corte de ciclo.** Um dump malformado
  com receita auto-referente não pode derrubar a API.
- **Elos deduplicados na resposta.** A recursão visita o mesmo tier por caminhos
  diferentes (T6 é insumo de T7 e de T8); repetir viraria borrão em vez de
  mostrar o gargalo.

## Notas da fase 7

- **O dump é irregular e precisa ser tratado, não assumido.**
  `craftingrequirements` pode ser objeto ou lista (receitas alternativas:
  `T4_PLANKS` sai de 2× madeira **ou** de 1× madeira + token). `craftresource`
  pode ser objeto, lista ou ausente.
- **Material encantado vem sem o sufixo de mercado.** O dump diz `T4_ROCK_LEVEL1`
  com `@enchantmentlevel: 1`; o catálogo e o AODP usam `T4_ROCK_LEVEL1@1`. Sem
  recompor isso, 12 mil materiais ficam órfãos e o custo de craft encantado sai
  errado para menos. Foi exatamente o que aconteceu na primeira importação.
- **`quantity` é `Integer`, não `SmallInteger`.** Existe receita pedindo 40.000
  unidades de um material. Descoberto importando o dump de verdade.
- **Material sem cotação derruba o craft inteiro.** Custo parcial não é custo
  menor — é custo desconhecido.
- **`cityresources` ficou fora do retorno de material.** É onde o dump coloca os
  tokens de facção, e token consumido quase certamente não volta. A
  classificação não foi verificada no jogo e entra na lista de `docs/04-taxas.md`;
  errar para menos retorno é o lado conservador.
- **O downgrade do seed falha se houver dado de mercado.** É o RESTRICT
  funcionando: reverter schema não pode apagar em silêncio a procedência de
  preços coletados.

## Notas da fase 6

- **Duas estratégias, taxas diferentes.** IMEDIATA consome ordens existentes e
  não paga setup fee. PACIENTE cria ordem nas duas pontas, paga setup duas vezes
  e paga mesmo que a ordem nunca execute. Tratar as duas igual é o erro que faz
  uma arbitragem "de 9%" virar prejuízo.
- **Margem e ROI medem coisas diferentes.** Margem sobre receita bruta, ROI sobre
  capital imobilizado. Margem alta com ROI baixo é armadilha de capital parado.
- **Score não é publicado com confiança abaixo de 50%.** Um smoke test mostrou
  score 97 "excelente" ao lado de "lucro desconhecido", porque só frescor e
  liquidez tinham dado. Um número alto ali dá confiança a uma oportunidade que
  ninguém avaliou — pior do que não ter score.
- **Componente ausente não pontua zero.** O peso é redistribuído e a confiança
  cai. Pontuar zero puniria item novo como se fosse ruim.
- **A idade exibida é a da ponta mais velha.** A operação só é tão confiável
  quanto o pior dos dois preços.
- **Black Market fora por padrão.** ~~Semântica de ordens invertida~~ — corrigido
  na fase 13: a suposição era falsa e ele entra como destino de venda. Ver as
  notas da fase 13.

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
