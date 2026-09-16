# 04 — Taxas de mercado: levantamento, ainda NÃO aplicado

> Pesquisa feita em 12/09/2026 para a FASE 6. **Nada disto foi gravado no banco.**
> `config_parameters` continua com `value = NULL` e `source = 'UNKNOWN'`, e há
> teste que falha se alguém preencher sem verificação (requisito 52).

## Por que este documento existe separado

Arbitragem, crafting e refino não existem sem imposto. Um erro de 2 pontos
percentuais numa margem de 8% não deixa o número "um pouco errado" — inverte o
sinal do lucro e a plataforma recomenda uma operação que perde prata.

## O que as fontes dizem

| Fonte | Setup fee | Imposto de venda |
|---|---|---|
| Wiki oficial (Marketplace) | citada, sem percentual explícito na página | **8%**, ou **4%** com Premium |
| Patch de teste (fórum, 2022) | setup e sales subiram de 3% + 1,5% para **4% + 2,5%** | — |
| Guia de flipping (2026) | **2,5%**, cobrado nas duas pernas | **4%** com Premium, **8%** sem |
| Calculadora de crafting (2026) | descreve **4% setup + 2,5% sales** com Premium | — |

## O conflito, que é o ponto

Os números **2,5%** e **4% / 8%** aparecem em todas as fontes. O que não bate é
**qual é qual**:

- a wiki oficial é explícita de que o **imposto de transação** é 8% (4% com
  Premium), o que implica setup fee de 2,5%;
- uma das calculadoras inverte os rótulos, chamando 4% de setup e 2,5% de sales.

A soma dá quase o mesmo total (6,5% com Premium), então a confusão passa
despercebida numa conta de ida e volta. **Mas não numa conta separada por perna:**
o setup fee é pago nas duas pontas e mesmo que a ordem não execute; o imposto de
venda só incide quando vende. Trocar os dois erra o custo de uma ordem de compra
que não fecha — exatamente o caso que mais aparece em arbitragem.

Há ainda um detalhe que nenhuma fonte quantifica com precisão: parte delas diz
que o setup fee **varia com a duração da listagem**. Se for verdade, não é uma
constante e sim uma função.

## O que precisa ser verificado no jogo

Cinco medições, todas de dentro do cliente:

1. Criar uma ordem de **venda** de valor redondo (ex.: 100.000) e anotar o débito
   imediato. Isso isola o setup fee.
2. Repetir com uma ordem de **compra** do mesmo valor. Confirma se o setup fee é
   igual nas duas pernas.
3. Deixar a venda executar e anotar o débito no momento da venda. Isso isola o
   imposto de transação.
4. Repetir 1 e 3 **sem** Premium, ou com Premium expirado, para confirmar qual
   dos dois dobra.
5. Criar a mesma ordem com durações diferentes de listagem e comparar o setup
   fee. Confirma se é constante ou função da duração.

Com 100.000 de valor, cada ponto percentual são 1.000 de prata — a diferença é
visível a olho nu no log de transações.

## Item 6 — retorno de material: de "sem fonte" para estimativa de alta fidelidade

> **Status em 16/09/2026:** os números estão gravados e os cálculos rodam. O item
> **continua aberto**, porque nada disto foi medido dentro do jogo.

### A matriz

| Atividade | Local | Sem Focus | Com Focus |
|---|---|---|---|
| Refino | cidade com bônus do recurso | **0,367** | **0,539** |
| Refino | sem bônus | 0,152 | 0,435 |
| Craft | cidade com bônus do item | **0,248** | **0,477** |
| Craft | sem bônus | 0,152 | 0,435 |

`source`, gravado em cada uma das oito chaves:

```
engenharia reversa da comunidade (logs de transacao + simulacao de alta
amostragem); albioncodex, albionfreemarket, albiononlinegrind; consultado em
16/09/2026; nao auditado contra codigo da Sandbox
```

### Por que 36,7% e não 40%

A documentação oficial cita **+40%** e a comunidade mediu **36,7%**. Os dois
estão certos: **não descrevem a mesma coisa.**

- O número oficial é o **bônus bruto** da estação — o modificador que o jogo
  aplica.
- O número da comunidade é o **efeito realizado**: quanto do material de fato
  volta para o inventário, depois de como o retorno é sorteado por unidade e
  arredondado.

É por isso que os números da comunidade têm casa decimal e o oficial é redondo:
um é parâmetro de sistema, o outro é resultado medido. Usar 40% no cálculo
superestimaria o retorno em ~9% relativos — e superestimar retorno é
superestimar lucro, que é o lado errado de errar neste projeto.

### O bônus por cidade

Refino segue o **recurso**, que segue o bioma:

| Cidade | Recurso |
|---|---|
| Fort Sterling | madeira / tábuas |
| Lymhurst | fibra / tecido |
| Bridgewatch | pedra / blocos |
| Martlock | couro / peles curtidas |
| Thetford | minério / barras |
| Caerleon | nenhum dos cinco básicos |

Craft segue a **família do item**, que é outra divisão. Conferido: em 9 de 9
peças de armadura, a cidade que refina o material **não** é a que dá bônus para
craftá-la. Isso não é inconsistência entre as duas tabelas — é o que obriga o
material a viajar.

Fonte do mapeamento de refino: guia oficial de refino da Albion Online +
tabelas de bônus locais de albiononlinegrind, consultados em 16/09/2026.

### O que continua aberto

1. **Medição direta no jogo.** Refinar um lote de tamanho conhecido na cidade
   com bônus e fora dela, com e sem Focus, e contar o material devolvido. É o
   que troca "estimativa de alta fidelidade" por "medido".
2. **O bônus de Focus.** A matriz traz o resultado com Focus, mas não a fórmula:
   não se sabe se o Focus multiplica o bônus da cidade ou soma a ele.
3. **O bônus diário de produção** (0, 10% ou 20%). O cálculo o soma à célula da
   matriz. A soma é a leitura mais simples e **não foi verificada**.
4. **Famílias de craft não mapeadas.** "Cajados de quartzo" não existe no dump; o
   candidato é `2H_QUARTERSTAFF` e a tradução não confirma. As linhas HALBERD,
   SCYTHE, GLAIVE, CLAWPAIR, FLAIL, KNUCKLES, SHAPESHIFTER e as de bastão também
   ficaram sem confirmação. Todas caem no retorno sem bônus — errar para menos.

## Sexto item para verificar: retorno de material

Além das cinco medições acima, a classificação de **quais materiais retornam** no
craft não foi verificada. O importador hoje trata `resources` e
`refinedresources` como elegíveis, e deixa `cityresources` de fora — é onde o
dump coloca os tokens de facção.

Medição: craftar um item cuja receita inclua token de facção, com retorno ativo,
e conferir se o token volta. Se voltar, incluir `cityresources` em
`RETURNABLE_SUBCATEGORIES`.

Errar para menos retorno subestima o lucro. É o lado conservador de errar.

## Sétimo ao décimo item: agricultura e criação

A fase de agricultura trouxe quatro leituras que o dump **não** decide sozinho.
Todas aparecem em `params.assumptions` na resposta de `/farming/plans`, para que
número interpretado não passe por número medido.

| # | O que verificar | Medição no jogo | Efeito de errar |
|---|---|---|---|
| 7 | Quantos ciclos de Focus uma criação aceita | Colocar um filhote no pasto e contar quantas vezes o Focus pode ser aplicado até ele virar adulto. Comparar com `@activefarmmaxcycles` | Prata/Focus de criação sai errada por um fator inteiro |
| 8 | O que `@activefarmbonus` multiplica | Colher o mesmo cultivo com e sem Focus e comparar a quantidade | Hoje o campo é gravado e **não** usado: o lucro sai subestimado, que é o lado conservador |
| 9 | Se a comida favorita (`@favoritebonus`) reduz o consumo | Criar dois filhotes iguais, um com a comida favorita e outro sem, e comparar a ração gasta | Custo de ração superestimado no caso favorito |
| 10 | Se o comerciante de fazenda vende semente e filhote a preço fixo para todos | Comprar uma semente no NPC e comparar com `craftingrequirements.@silver` do dump | Hoje o cálculo usa o preço de mercado e mostra o valor do NPC ao lado; se o NPC for sempre mais barato, o custo real é menor que o exibido |

O que **não** precisa de medição, porque o dump diz literalmente: a duração do
ciclo (79.200 s = 22 h), o tempo de crescimento de cada filhote, o consumo de
nutrição (`@secondspernutrition`) e a faixa da colheita (`3-6` por pé, em
`loot.json`).

## Como gravar depois

```sql
UPDATE config_parameters
SET value = '0.025'::jsonb,
    source = 'medido no jogo em 2026-09-XX, ordem de 100k em Caerleon'
WHERE key = 'market.sell_order_setup_fee_pct';
```

A coluna `source` não é decoração: ela é o que permite, seis meses depois,
descobrir que o número veio de um patch antigo. Nunca gravar com
`source = 'UNKNOWN'` preenchido, e nunca gravar um valor "de internet" sem dizer
de qual página e de que data.

## Como a fase 6 resolveu isso

Sem esperar pela medição, e melhor do que o plano original: **a taxa é entrada do
usuário.** O imposto depende de a conta ter Premium, então um valor único de
servidor estaria errado para metade das pessoas de qualquer jeito.

Precedência:

```
parâmetro da requisição  →  config_parameters  →  UNKNOWN
```

- `calculations/fees.py` recebe `FeeProfile` como argumento obrigatório e nunca
  lê configuração;
- sem taxa, `economics.known = false` e o `reason` diz exatamente qual chave
  falta;
- o spread bruto continua visível, rotulado como bruto — é o número que engana
  quando mostrado sozinho;
- a resposta carrega as taxas usadas e a origem delas (`usuario` / `config`),
  para que um lucro de 18% seja auditável.

As cinco medições continuam valendo: elas definem o **padrão** que aparece
pré-preenchido para quem não quiser configurar nada. Mas não travam mais o
produto.
