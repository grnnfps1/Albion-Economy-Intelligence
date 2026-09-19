# 02 — AODP: o que foi verificado

> Verificado em **12/09/2026** contra `https://pow.albion-online-data.com/api` e contra
> respostas reais da API. Isto não é cópia da documentação antiga — cada formato abaixo
> veio de uma chamada executada.

## Hosts

| Servidor | Base URL |
|---|---|
| Americas / West | `https://west.albion-online-data.com` |
| Asia / East | `https://east.albion-online-data.com` |
| Europe | `https://europe.albion-online-data.com` |

## Endpoints usados

### Preço atual
```
GET /api/v2/stats/prices/{item_ids}.json?locations=A,B&qualities=1,2
```
Resposta real (`T4_BAG`, Caerleon, quality 2):
```json
[{
  "item_id": "T4_BAG", "city": "Caerleon", "quality": 2,
  "sell_price_min": 6388, "sell_price_min_date": "2026-09-10T00:30:00",
  "sell_price_max": 6486, "sell_price_max_date": "2026-09-10T00:30:00",
  "buy_price_min": 0,    "buy_price_min_date": "0001-01-01T00:00:00",
  "buy_price_max": 0,    "buy_price_max_date": "0001-01-01T00:00:00"
}]
```
Campo é `city`, não `location`. Quatro pares preço/data independentes.

### Histórico (só sell orders)
```
GET /api/v2/stats/history/{item_ids}.json?locations=A&qualities=2&time-scale=24
```
`time-scale`: `1` = hora, `6` = 6h, `24` = dia. Resposta real:
```json
[{
  "location": "Black Market", "item_id": "T4_BAG", "quality": 1,
  "data": [{ "item_count": 424, "avg_price": 4425, "timestamp": "2026-08-13T00:00:00" }]
}]
```
Campo é `location` aqui e `city` no endpoint de preços. Estrutura aninhada, não plana.
Duas normalizações diferentes.

### Gold
```
GET /api/v2/stats/gold.json?count=N
GET /api/v2/stats/gold.json?date=YYYY-MM-DD&end_date=YYYY-MM-DD
```
Resposta real:
```json
[{"price": 8000, "timestamp": "2026-09-12T21:00:00"}]
```
Sem campo de servidor — o servidor é o host da requisição. Portanto `server_id` vem do
collector, não do payload.

### Charts
`/api/v2/stats/charts/{item_ids}.json?...` — mesma informação de history em formato
colunar. **Não vamos usar**: history já entrega tudo, e ter dois parsers para o mesmo
dado é dívida gratuita.

### Volume diário — não existe endpoint próprio

> Verificado em **19/09/2026**, contra a documentação da API e contra chamadas reais.

A planilha do Albion VIP tem um feed de volume separado do histórico, e a pergunta
era se o AODP expõe algo equivalente. **Não expõe.** Os endpoints documentados são
cinco — `view`, `prices`, `history`, `charts` e `gold` — e nenhum deles é de volume.

`charts` foi conferido lado a lado com `history` para o mesmo item, local e escala:

```
GET /api/v2/stats/charts/T4_BAG.json?locations=Caerleon&qualities=1&time-scale=24
→ data: { "timestamps": [...], "prices_avg": [...], "item_count": [...] }

GET /api/v2/stats/history/T4_BAG.json?locations=Caerleon&qualities=1&time-scale=24
→ data: [ { "item_count": 105, "avg_price": 5191, "timestamp": "..." }, ... ]
```

As três séries são as mesmas, nos mesmos 30 pontos e com os mesmos valores
(`item_count` 105, 128, 81 … em ambos). A única diferença é a forma: colunar em
`charts`, uma linha por bucket em `history`.

**Conclusão: nada muda.** `item_count` do histórico continua sendo a única medida de
volume que a fonte oferece, e é a que `repositories/liquidity.py` já usa. Trocar de
endpoint só acrescentaria um segundo parser para o mesmo dado.

Vale repetir a ressalva que já vale para o preço: `item_count` conta **ordens de
venda** registradas pela coleta comunitária, não transações fechadas. Bucket marcado
como outlier fica fora do cálculo de liquidez — pico manipulado costuma vir com
volume igualmente irreal —, e menos de 3 buckets na janela devolve `UNKNOWN`.

## Rate limit — a restrição que define o scheduler

Documentado: **180 req / 1 min** e **300 req / 5 min**.

O segundo limite é o que manda. 300/5min = **1 req/s sustentado**. O limite de 180/min
só permite um burst curto; quem dispara 180 num minuto fica com 120 para os 4 minutos
seguintes. O rate limiter precisa implementar **as duas janelas simultaneamente** — só a
de 1 min passa despercebido e leva a 429 no minuto 3.

Orçamento diário: ~86.400 requisições. Com ~200 itens × 8 locais em um request, uma
varredura completa do catálogo útil cabe em poucos minutos por servidor.

## Limites de requisição

- **URL máx. 4096 caracteres.** O batcher monta lotes pelo comprimento da URL final,
  não por contagem de itens — `T8_2H_HOLYSTAFF_MORGANA@3` e `T4_BAG` têm tamanhos muito
  diferentes.
- **Gzip obrigatório para uso contínuo.** O projeto pede explicitamente. `Accept-Encoding:
  gzip` em todo request e `User-Agent` identificando a aplicação e um contato.

## Armadilhas de normalização

1. **Sentinela.** `price == 0` com data `0001-01-01T00:00:00` = não existe ordem → `NULL`.
   Tratar como zero produz margem infinita.
2. **Timestamps naive.** Vêm sem fuso e são UTC. Anexar UTC explicitamente antes de
   gravar; deixar o driver assumir o fuso do servidor é bug silencioso.
3. **Nomes com espaço.** `Fort Sterling`, `Black Market` — chave de lookup é a string
   exata do AODP, guardada em `locations.aodp_name`.
4. **Preço e sua data são independentes.** `sell_price_min_date` pode ser de hoje e
   `buy_price_max_date` de três dias atrás na mesma linha. A idade é por campo.
5. **Buy/sell são coisas distintas** (item 13). Quem compra do mercado paga
   `sell_price_min`; quem vende instantaneamente recebe `buy_price_max`.

## Outliers no histórico — problema real, não hipotético

Na validação, `T4_BAG` quality 2 em Lymhurst:
`3.625` (15/08) → **`29.790`** (16/08) → `3.737` (17/08).

Um único registro caro contamina a média do bucket. Como o endpoint devolve `avg_price`
(não mediana), qualquer "preço médio 7d" ingênuo herda o lixo — e a plataforma anuncia
uma oportunidade que não existe.

Mitigação: guardar o valor cru, marcar `is_outlier` por mediana + MAD dentro da janela
`(item, location, quality)`, e usar **mediana** nas médias de referência. A UI mostra o
ponto marcado, não o apaga.

## Natureza do dado

Os dados vêm de coleta comunitária: alguém precisa ter aberto aquele mercado no jogo com
o client rodando. Consequências que a UI **precisa** comunicar (itens 4 e 21):

- ausência de preço ≠ preço baixo;
- mercado pouco visitado tem dado velho e liquidez desconhecida;
- nenhuma cotação é garantida.

Por isso `liquidity_status = UNKNOWN` é um estado de primeira classe, não um erro.

## Black Market — validado empiricamente em 16/09/2026

A suposição que estava aqui era de que **a semântica de ordens é invertida**. A
consulta real desmentiu isso. O que segue substitui o texto anterior.

### A consulta

`GET /api/v2/stats/prices/{40 equipamentos T4–T7}?locations=Black Market,Caerleon&qualities=1`,
servidor west, 16/09/2026. 40 linhas de cada local. Uma segunda rodada incluiu 7
recursos (`T4_PLANKS`, `T5_METALBAR`, `T4_LEATHER`, `T6_CLOTH`, `T4_WOOD`,
`T5_ORE`, `T5_PLANKS`).

### O que o AODP preenche

| | `sell_price_min` | `buy_price_max` | idade mediana |
|---|---|---|---|
| Black Market | 38/40 | **40/40** | 1,2 h |
| Caerleon | 37/40 | 4/40 | 11,8 h |

Quatro conclusões, todas com número atrás:

1. **O campo que o Black Market sempre preenche é `buy_price_max`** — 40 de 40,
   contra 4 de 40 em Caerleon. É o que se espera de um local onde as ordens de
   compra são de NPC e estão sempre lá. É também o campo que interessa para
   vender: quem vende na hora recebe `buy_price_max` (regra 7 do CLAUDE.md), e
   isso vale no Black Market exatamente como numa cidade.

2. **A orientação é normal, não invertida.** Em 38 linhas com os dois preços,
   `sell_price_min >= buy_price_max` em **38 de 38**. Nenhuma inversão. A nota
   antiga estava errada e foi removida — nenhum tratamento especial de sinal é
   necessário.

3. **O Black Market não negocia recurso.** Dos 7 recursos consultados, os quatro
   campos vieram zerados em 7 de 7. Ele só tem linha para equipamento. Não é
   regra de negócio nossa: é ausência de dado, e o cálculo trata como sempre —
   sem cotação, resultado `UNKNOWN`.

4. **O dado do Black Market é mais fresco que o da cidade** (1,2 h contra 11,8 h
   na mediana), porque é um local muito visitado. Isso inverte a intuição: o
   ponto mais arriscado da rota costuma ter o preço mais confiável.

Para calibrar a expectativa: `buy_price_max` do Black Market é, na mediana,
**0,77×** o `sell_price_min` de Caerleon (n=37; mínimo 0,07×, máximo 1,29×).
Vender na hora no Black Market costuma render menos do que listar na cidade —
mas executa na hora, sem esperar comprador, e em alguns itens paga mais.

O campo de local continua sendo `city` neste endpoint, inclusive para o Black
Market (o histórico é que chama de `location`).

### O que isso libera, e o que continua fora

Com a validação feita, o Black Market entra como **destino de venda** em
`/arbitrage` e `/crafting`.

Continua **fora como origem de compra**: as 40 linhas mostram que ele tem ordens
de venda listadas, mas comprar equipamento lá para revender não foi medido, e a
regra do projeto é não habilitar perna não verificada. Vender é o que foi
validado; comprar fica para uma medição própria.

E vender no Black Market não é de graça: ele fica em zona vermelha/preta. Ver
`transport_routes` e o lucro ajustado ao risco em `docs/01-modelo-de-dados.md`.

## Catálogo de itens

O AODP **não** fornece metadados de item. A fonte é
`github.com/ao-data/ao-bin-dumps` → `formatted/items.json` e `formatted/world.json`.
São arquivos grandes e mudam por patch: baixar no deploy/seed, versionar o hash, nunca
buscar em runtime a cada request.

## Como o client implementa isso (fase 3)

`backend/app/collectors/aodp/`. Os pontos acima viraram código e teste:

| Armadilha | Onde mora a defesa |
|---|---|
| sentinela `0` + `0001-01-01` | `normalization.normalize_price` → `(None, None)` |
| timestamp sem fuso | `normalization.to_utc` |
| `city` vs `location` | dois schemas distintos em `schemas.py` |
| limite de 4096 caracteres | `batching.batch_item_names`, medindo a URL codificada |
| janela dupla de rate limit | `rate_limit.SlidingWindowRateLimiter` |
| 429 | `Retry-After` respeitado; backoff com jitter como alternativa |
| mudança de contrato | validação estrita + `AodpInvalidPayload` com o bruto |

## A verificar na Fase 4

- Comportamento de `qualities=0` (existem usos na comunidade sugerindo "todas") — medir,
  não assumir.
- Se o histórico realmente ignora `locations` quando o parâmetro é omitido (o teste
  retornou todas as cidades).
- Presença de header `Retry-After` no 429.
- Latência p95 por host, para dimensionar timeout.
