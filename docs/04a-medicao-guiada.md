# 04a — Como medir as taxas dentro do jogo

Complemento prático de `docs/04-taxas.md`, que lista **o que** precisa ser
medido. Este documento diz **como**, passo a passo, e traz a planilha em branco
para anotar.

Nada aqui contém valor medido: os campos estão vazios de propósito. Preencher
este arquivo com número de wiki ou de fórum reintroduz exatamente o problema que
`04-taxas.md` documenta — as fontes divergem entre si sobre qual taxa é qual.

## O método: diferença de saldo, não rótulo de tela

Toda medição abaixo se apoia numa única coisa observável: **o saldo de prata
antes e depois da ação**. É deliberado.

A tela de criação de ordem mostra uma estimativa de taxa, e é tentador anotar
aquele número. O problema é que ele é um rótulo — não prova o que foi de fato
debitado, não distingue setup fee de imposto, e muda de nome entre versões do
cliente. O saldo, não: se saíram 2.500 de prata, saíram 2.500.

Regra para todas as medições: **anote o saldo com o número cheio**, não o
abreviado do cabeçalho. Um `1,2m` no canto da tela esconde exatamente a casa
decimal que estamos tentando medir.

Use **100.000** como valor de referência sempre que possível: cada ponto
percentual vira 1.000 de prata, visível a olho nu.

## Antes de começar

- Faça tudo **numa cidade só** e anote qual. Taxa de estação varia por cidade, e
  a de mercado precisa ser confirmada como não variando.
- Anote se a conta está **com Premium** em cada medição. É a variável que a
  plataforma mais precisa separar.
- Anote a **data**. As taxas já mudaram por patch antes.
- Tire print de cada saldo. A medição vale pelo que dá para auditar depois.

---

## Medição 1 — setup fee da ordem de venda

O objetivo é isolar o setup fee, então a ordem **não pode executar**.

1. Anote o saldo: `S0 = ____________`
2. Escolha um item barato e crie uma **ordem de venda** de 1 unidade por
   **100.000** de prata — preço absurdamente acima do mercado, para que ninguém
   compre.
3. Anote o saldo imediatamente após confirmar: `S1 = ____________`
4. **Setup fee = S0 − S1 = ____________**, ou seja `______ %` de 100.000.

Se o débito for zero, o setup fee não é cobrado na criação e sim na execução — o
que mudaria a modelagem de `calculations/fees.py`. Anote: é resultado, não erro.

## Medição 2 — setup fee da ordem de compra

Confirma se a taxa é igual nas duas pernas. É o que a estratégia PACIENTE assume.

1. Anote o saldo: `S0 = ____________`
2. Crie uma **ordem de compra** de 1 unidade por **100.000** de prata de um item
   que custe bem mais que isso — assim a ordem fica aberta sem executar.
3. Anote o saldo: `S1 = ____________`

Atenção a uma armadilha: a ordem de compra provavelmente **reserva** os 100.000
além de cobrar a taxa. Então:

- **Diferença total = S0 − S1 = ____________**
- Se a diferença for maior que 100.000, o excedente é a taxa:
  **setup fee = (S0 − S1) − 100.000 = ____________**
- Se for exatamente 100.000, não houve taxa na criação da ordem de compra.

4. **Cancele a ordem** e anote o saldo: `S2 = ____________`
   - Se `S2 = S1 + 100.000`, a reserva volta e **a taxa não volta** — é custo
     afundado, e é exatamente o que `fees.py` assume ao cobrar setup fee mesmo em
     ordem que nunca executa.
   - Se `S2` voltar ao valor de `S0`, a taxa é devolvida no cancelamento, e a
     modelagem da estratégia PACIENTE está errada. Anote.

## Medição 3 — imposto de venda

Aqui a ordem **precisa** executar.

1. Anote o saldo: `S0 = ____________`
2. Venda um item **na hora**, aceitando uma ordem de compra existente, sem criar
   ordem. Anote o preço bruto da ordem aceita: `P = ____________`
3. Anote o saldo: `S1 = ____________`
4. **Recebido = S1 − S0 = ____________**
5. **Imposto = 1 − (recebido ÷ P) = ______ %**

Esta medição rende um segundo resultado de graça: se `recebido = P × (1 − imposto)`
sem nenhum desconto extra, fica confirmado que **venda imediata não paga setup
fee** — a premissa da estratégia IMEDIATA em `calculations/fees.py`.

## Medição 4 — com e sem Premium

Repita as medições 1 e 3 com o status de Premium invertido.

| | Com Premium | Sem Premium |
|---|---|---|
| setup fee | `__________` | `__________` |
| imposto de venda | `__________` | `__________` |

O que se quer saber é **qual dos dois dobra**. As fontes divergem justamente
nisso, e é o erro que inverte o sinal do lucro numa margem baixa.

Se não houver como desativar o Premium, esta medição fica pendente — anote como
pendente em vez de deduzir. Meia medição registrada como completa é pior que
nenhuma.

## Medição 5 — o setup fee depende da duração?

Repita a medição 1 três vezes, mesmo valor de 100.000, mudando só a duração da
listagem:

| Duração | Setup fee |
|---|---|
| mais curta disponível | `__________` |
| intermediária | `__________` |
| mais longa disponível | `__________` |

Se variar, **não é constante e sim função da duração** — e aí
`market.sell_order_setup_fee_pct` precisa deixar de ser um número.

---

## Medição 6 — taxa de retorno de recurso (RRR)

Esta é **probabilística**, e é a diferença mais importante entre ela e as
anteriores: o retorno é sorteado por unidade produzida. Craftar 5 itens e dividir
não mede a taxa — mede o sorteio daquele dia.

1. Escolha uma receita simples e anote o consumo por craft:
   `consumo esperado por craft = ____________`
2. Anote o estoque do material: `M0 = ____________`
3. Faça **pelo menos 100 crafts** seguidos. Quanto mais, menor o ruído.
   Número de crafts: `N = ____________`
4. Anote o estoque: `M1 = ____________`
5. **Consumido = M0 − M1 = ____________**
6. **RRR = 1 − (consumido ÷ (N × consumo esperado)) = ______ %**

Repita **com Focus** e **sem Focus**, na mesma estação, cidade e nível de
especialização:

| | Sem Focus | Com Focus |
|---|---|---|
| N (crafts) | `__________` | `__________` |
| RRR medida | `__________` | `__________` |

Anote também **cidade e estação**: bônus de cidade entra nessa conta, então o
número medido vale para aquela combinação e não é global.

### O que a especialização faz — e o que ela não faz

Ponto levantado durante a fase de medição, **ainda não verificado por nós**:
subir especialização **não aumenta a RRR**; o que ela reduz é o **custo de Focus
por unidade**. O efeito prático é que o mesmo pool de Focus rende mais crafts
focados, então o retorno **total** de recursos sobe enquanto a **taxa** fica a
mesma.

Se isso se confirmar, a modelagem atual do projeto já está certa e a
especialização não pertence à RRR:

- a RRR é uma taxa, medida aqui na medição 6;
- a especialização pertence a `focus_per_unit`, consumido por
  `calculations/focus.py` — que é justamente onde "prata por Focus" é calculado.

Consequência para quem for medir: **mantenha a especialização constante dentro
de uma mesma medição de RRR**, e trate o custo de Focus como medição separada
(medição 9). Misturar as duas produz uma RRR que parece variar com spec quando
na verdade quem variou foi o denominador.

## Medição 7 — taxa da estação

1. Anote a taxa afixada pela estação: `____________`
2. Anote o saldo antes: `S0 = ____________`
3. Faça `N = ______` crafts.
4. Anote o saldo depois, **descontando o que foi gasto em material**:
   `S1 = ____________`
5. **Custo de estação por craft = (S0 − S1) ÷ N = ____________**

O que se quer descobrir é a **unidade**: a taxa afixada é por craft, por item
produzido, ou proporcional a algum peso da receita? É isso que
`crafting.station_fee_formula` está esperando, e é por isso que a chave tem
`_formula` no nome e não `_pct`.

## Medição 8 — token de facção retorna?

1. Crafte um item cuja receita inclua **token de facção**, com retorno ativo.
2. O token voltou? `sim / não`

Se voltou, incluir `cityresources` em `RETURNABLE_SUBCATEGORIES` no importador de
receitas. Hoje está de fora, o que **subestima** o lucro — o lado conservador de
errar.

## Medição 9 — custo de Focus por craft

Separada da medição 6 de propósito, pelo motivo explicado acima.

1. Anote o Focus disponível: `F0 = ____________`
2. Faça `N = ______` crafts focados do **mesmo item**, mesma estação.
3. Anote o Focus restante: `F1 = ____________`
4. **Focus por craft = (F0 − F1) ÷ N = ____________**
5. Anote o **nível de especialização** naquele item: `____________`

Repita em pelo menos dois níveis de especialização diferentes:

| Especialização | Focus por craft | RRR medida |
|---|---|---|
| `__________` | `__________` | `__________` |
| `__________` | `__________` | `__________` |

Se o Focus por craft cair e a RRR ficar igual, o ponto da seção anterior está
confirmado — e vale registrar isso no `source`, porque é uma decisão de
modelagem, não só um número.

---

## Gravando o resultado

Só grave o que foi medido. Chave sem medição continua `NULL` com
`source = 'UNKNOWN'`: é melhor a tela dizer "não configurado" do que exibir um
palpite com cara de fato.

```sql
UPDATE config_parameters
SET value = '0.0XX'::jsonb,
    source = 'medido no jogo em 2026-XX-XX, ordem de 100k em <cidade>, conta <com/sem> Premium'
WHERE key = 'market.sell_order_setup_fee_pct';
```

Repita por chave:

| Chave | Vem da medição |
|---|---|
| `market.sell_order_setup_fee_pct` | 1, confirmada por 2 e 5 |
| `market.sales_tax_pct.premium` | 3 com Premium |
| `market.sales_tax_pct.standard` | 3 sem Premium |
| `crafting.return_rate.base` | 6 sem Focus |
| `crafting.return_rate.focus` | 6 com Focus |
| `crafting.station_fee_formula` | 7 |
| `refining.return_rate.base` | 6 aplicada a refino |
| `refining.return_rate.focus` | 6 aplicada a refino, com Focus |

O `source` não é decoração: é o que permite, seis meses e dois patches depois,
descobrir que o número veio de uma medição velha. Escreva nele a data, a cidade e
o status de Premium.

## Depois de gravar

Os valores no banco viram o **padrão pré-preenchido**, não uma trava: a
precedência continua `parâmetro da requisição → config_parameters → UNKNOWN`, e
quem tiver Premium diferente do medido continua ajustando na tela. O que muda é
que o padrão deixa de ser palpite da comunidade e passa a ser medição, com
procedência auditável.
