# 04 — Taxas de mercado: levantamento, ainda NÃO aplicado

> Pesquisa feita em 12/09/2026 para a FASE 6. Os itens 1 a 5 (mercado)
> **continuam com `value = NULL` e `source = 'UNKNOWN'`** em
> `config_parameters`, e há teste que falha se alguém preencher sem
> verificação (requisito 52). Os itens 6 e 11 ganharam valor com procedência
> declarada nas fases 14 e 15 — procedência não é medição, e eles seguem
> abertos.
>
> **Prioridade de medição (revista em 19/09/2026):**
>
> 1. **Itens 1 a 5 — taxas de mercado.** São os únicos desta lista **sem
>    nenhuma fonte confiável**: o que existe são fontes que *se contradizem*
>    entre si sobre qual percentual é setup fee e qual é imposto de venda. Não
>    há anúncio oficial, não há validação independente, e um erro de 2 pontos
>    numa margem de 8% inverte o sinal do lucro. Continuam `NULL`/`UNKNOWN` no
>    banco.
> 2. ~~**Item 6 — retorno de material.**~~ **Fechado em 19/09/2026**: a
>    contradição entre os +40% oficiais e os 36,7% medidos era aparente, e
>    `RRR = B/(1+B)` reproduz os cenários publicados.
> 3. **Itens 7 a 10 — agricultura**, e o **item 14** (bônus diário), que a
>    tentativa da fase 20 não resolveu.
> 4. **Item 11 — taxa da estação.** Já foi prioridade 1; **deixou de ser.**
>    Ganhou confirmação independente em duas abas da planilha do Albion VIP,
>    além do anúncio oficial da Sandbox. A medição continua valendo — é a única
>    que não depende de terceiro —, mas não é mais a mais urgente.

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

## Item 6 — retorno de material: RESOLVIDO pela fórmula

> **Status em 19/09/2026: fechado.** A contradição que mantinha este item aberto
> era **aparente**, e a fórmula que a desfaz reproduz todos os cenários
> publicados. O que continua em aberto é só o bônus diário, que virou item 14.

### A contradição era aparente

O impasse era este: a documentação oficial fala em **+40% de bônus** de refino
na cidade do recurso, e a comunidade mede **36,7% de retorno**. Por dois meses
isto ficou registrado como "36,7% e 40% não se contradizem, mas não sabemos a
conversão".

A conversão é:

```
RRR = B ÷ (1 + B)
```

`0,58 ÷ 1,58 = 0,367`. Os dois números medem coisas diferentes, e agora está
claro quais: **`B` é o que a estação soma** e **`RRR` é a fração das unidades
que volta**. É por isso que o número oficial é redondo e o da comunidade tem
decimal — um é parâmetro, o outro é resultado.

### Os quatro componentes

| Componente | Valor | Quando entra | Chave |
|---|---|---|---|
| base de cidade | **+18%** | sempre, exceto em ilha | `crafting.return_bonus.city_base` |
| refino da cidade | **+40%** | refinando na cidade do recurso | `refining.return_bonus.city` |
| craft da cidade | **+15%** | craftando na cidade da família | `crafting.return_bonus.city` |
| foco | **+59%** | com Focus | `crafting.return_bonus.focus` |

Os bônus **somam antes da conversão**, não depois. Somar as taxas convertidas
daria `0,152 + 0,367 + 0,435 = 0,954`, que é quase o dobro do correto.

### Conferência contra o que a comunidade mediu

| Cenário | B | Fórmula | Medido | Desvio |
|---|---|---|---|---|
| refino, sem bônus, sem foco | 0,18 | 0,15254 | 0,152 | +0,00054 |
| refino, com bônus, sem foco | 0,58 | 0,36709 | 0,367 | +0,00009 |
| refino, sem bônus, com foco | 0,77 | 0,43503 | 0,435 | +0,00003 |
| refino, com bônus, com foco | 1,17 | 0,53917 | 0,539 | +0,00017 |
| craft, com bônus, sem foco | 0,33 | 0,24812 | 0,248 | +0,00012 |
| **craft, com bônus, com foco** | **0,92** | **0,47917** | **0,477** | **+0,00217** |
| ilha, sem foco | 0,00 | 0,00000 | 0 | 0 |
| ilha, com foco | 0,59 | 0,37107 | 0,371 | +0,00007 |

**Sete dos oito fecham abaixo de 0,0006.** O oitavo — craft com bônus de cidade
**e** foco — desvia **0,0022**, dez vezes mais que qualquer outro. Conclusão: é
o valor que a fase 14 tabelou que estava impreciso, não a fórmula. A célula
passou a valer **0,479**.

Isso é o oposto do que aconteceu no item 11: lá eu descartei uma fórmula com
fonte oficial por causa de números reconstruídos; aqui a fórmula corrige um
número tabelado. A diferença é que a fórmula reproduz sete de oito, e nenhuma
reconstrução reproduzia mais de uma.

### Ilha

Ilha não tem a base de cidade — `B` começa em zero. Consequência direta:

- **sem Focus: 0% de retorno.** Nada volta;
- **com Focus: 37,1%** (`0,59 ÷ 1,59`).

Ela entra no cadastro como local com `kind = 'island'`, **inativa para coleta**
e sem ordens de compra: ilha não tem mercado. É escolha de *onde produzir*, não
de *onde comprar* — quem produz na ilha compra numa cidade e carrega, e a tela
trata as duas como coisas separadas.

### O que mudou no código

A matriz de oito células saiu de `config_parameters` (migration 0011). Guardar a
tabela **e** a fórmula deixaria as duas divergirem no primeiro ajuste; agora se
guarda o parâmetro e deriva-se o resultado. `calculations/returns.py` é a
fórmula, e a resposta carrega `bonus_total` para a conta poder ser refeita na
mão.

## Item 15 — quais materiais retornam

> Pergunta diferente da do item 6, e por isso continua aberta. O item 6 era
> *qual é a taxa*; este é *sobre o que ela incide*.

A classificação de **quais materiais retornam** no craft não foi verificada. O importador hoje trata `resources` e
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

---

## Item 11 — taxa da estação: derivada do valor do item (fase 15)

> **Status: CONFIRMADO.** Fonte oficial da Sandbox **mais** validação
> independente em duas abas da planilha do Albion VIP, somando 49 linhas.
> Levantado em 19/09/2026, validado no mesmo dia contra o arquivo completo.
>
> **Correção de uma conclusão anterior deste documento.** Até 19/09/2026 esta
> seção afirmava que a fórmula "não reproduz os valores observados na planilha".
> **Isso estava errado, e o erro era meu, não da fórmula.** O detalhe de como
> aconteceu está em "O que eu errei", logo abaixo — vale mais que a conclusão,
> porque é reaproveitável.
>
> **A fórmula está confirmada; o parâmetro do usuário, não.** A prata por 100 de
> nutrição é escolha do dono da estação e **nasce vazia** na interface — é o
> único parâmetro sem padrão pré-preenchido no produto. Ver "Decisão: o campo
> nasce vazio".

### O que eu errei

Reconstruí a taxa da estação como **resíduo de subtração**: peguei o custo total
de uma coluna agregada, tirei os materiais e o retorno, e chamei o que sobrou de
"taxa da estação". Deu 5,17 no T2, 29,98 no T4 e 2.496,79 no T8 — números que
nenhuma taxa única explica.

**A planilha tinha a taxa numa coluna própria o tempo todo.** Duas, na verdade:
`BD_Itens_Craft.Taxa Loja` e `Crafters.Taxa da Loja`. Eu não procurei, porque
já tinha um número e ele parecia ser o número.

Quando os três resíduos não fecharam, tirei a conclusão errada — "a fórmula não
é validada pelos dados" — em vez da certa: **"o que estou chamando de taxa não é
a taxa"**. Um resíduo de subtração não é uma grandeza. Ele é a soma de tudo que
eu não modelei mais o erro de tudo que modelei errado, e não tem obrigação
nenhuma de se comportar como a grandeza que eu esperava.

A regra que fica: **quando a conta não fecha, a primeira hipótese é que a coluna
certa está em outro lugar, não que a fórmula está errada.** Procurar a coluna é
barato; refutar uma fórmula com fonte oficial deveria exigir muito mais do que
três números reconstruídos de segunda mão.

### A validação, em duas abas independentes

**`BD_Itens_Craft`, coluna "Taxa Loja"** — um coeficiente por item:

| Item | Taxa Loja | `@itemvalue` | ÷ iv × 100 |
|---|---|---|---|
| `T3_LEATHER` | 0,008958333 | 8 | 0,11198 |
| `T4_LEATHER` | 0,018020833 | 16 | 0,11263 |
| `T4_LEATHER_LEVEL2@2` | 0,071979167 | 64 | 0,11247 |
| `T6_LEATHER_LEVEL4@4` | 1,151724138 | 1024 | 0,11247 |
| `T8_LEATHER_LEVEL2@2` | 1,151979167 | 1024 | 0,11250 |

**23 de 24 linhas dão 0,1125** (±0,0005). A coluna é `item_value × 0,1125 ÷ 100`
— a nutrição por execução, pronta para multiplicar pela prata por 100.

**`Crafters`, coluna "Taxa da Loja"** — contra o valor que a própria planilha
declara (`Taxa da Loja = 184`, em `Crafters` L16 e no `Menu`), com produção
diária de 139:

```
F = taxa × 100 ÷ (item_value × 0,1125 × 139)
```

| Tier | Taxa da Loja | `@itemvalue` | F implicado |
|---|---|---|---|
| T4.0 | 460,901 | 16 | 184,21 |
| T5.0 | 921,802 | 32 | 184,21 |
| T6.3 | 14.732,842 | 512 | 184,01 |
| T7.4 | 58.912,993 | 2048 | 183,96 |
| T8.4 | 117.855,384 | 4096 | **184,00** |

**26 de 27 linhas caem entre 183,9 e 184,3**, contra os 184 declarados.

**A linha que não fechou:** `T5.4` destoa nas **duas** conferências, com o mesmo
desvio proporcional (F de 147,24; razão de 0,0900). Mesma linha, mesmo desvio,
abas diferentes — é consistente com uma célula errada na planilha, não com a
fórmula. Fica registrado sem explicação inventada.

O mapa completo do arquivo está em `docs/05-planilha-referencia.md`.

### O problema

A taxa da estação era `crafting.station_fee`, um número fixo de prata por
execução, com padrão 100. O sinal de que isso estava errado veio de uma
reconstrução do refino de couro — o resíduo depois de materiais e retorno
escalava com o tier (5,17 no T2, 29,98 no T4, 2.496,79 no T8), quando um valor
fixo é o mesmo em todos.

**O sinal estava certo; os números, não.** Aquele resíduo não era a taxa (ver
"O que eu errei"). Mas a conclusão que ele motivou — *taxa fixa não pode estar
certa, porque o custo de estação claramente cresce com o tier* — era válida, e é
confirmada pela coluna correta: a taxa vai de 4,5 no T2 a 288 no T8 com a mesma
estação. Um valor único erra por duas ordens de grandeza entre as pontas, para
menos no T8 — que é o lado que infla lucro.

### A mecânica, com fonte

O jogo não cobra por execução: cobra por **nutrição consumida**. Citando o
anúncio do patch *Lands Awakened*:

> "Usage Fees are now derived directly from the Nutrition an Item consumes when
> it is crafted/studied at a building"
> "Nutrition Cost = Item Value * 0.1125"
> "Usage Fees are now set as an amount of Silver per 100 Nutrition consumed"

Logo:

```
nutricao = item_value × 0,1125
taxa     = nutricao × (prata_por_100_nutricao ÷ 100)
```

O exemplo que circula desde então: 4.1 Scholar Sandals, item value 256, estação
cobrando 1.000 → `256 × 0,1125 × 1000 ÷ 100` = **288** de prata. Há teste
ancorado nesse exemplo (`test_exemplo_da_comunidade_fecha`).

### `@itemvalue` existe no dump, e é limpo

Conferido em 19/09/2026 contra `ao-data/ao-bin-dumps`:

| Item | `@itemvalue` |
|---|---|
| `T2_LEATHER` | 4 |
| `T3_LEATHER` | 8 |
| `T4_LEATHER` | 16 |
| `T5_LEATHER` | 32 |
| `T6_LEATHER` | 64 |
| `T7_LEATHER` | 128 |
| `T8_LEATHER` | 256 |
| `T8_LEATHER_LEVEL2` | 1.024 |
| `T8_LEATHER_LEVEL4` | 4.096 |

Dobra a cada tier **e** a cada nível de encantamento — exatamente os dois eixos
em que a taxa precisava escalar.

Cobertura: **2.398** dos 12.237 identificadores têm o campo; **358 dos 455
rastreados**. Os 97 rastreados sem `@itemvalue` são animais de pasto e
ferramentas de rastreamento, que não passam por estação de crafting. Neles a
taxa sai `UNKNOWN`, nunca zero.

### Os três resíduos, e por que eles não refutam nada

Ficam registrados porque a conclusão errada que saiu deles é mais instrutiva que
os números.

| Tier | Resíduo reconstruído | Item value | Prata/100 nutrição que ele implicaria |
|---|---|---|---|
| T2 | 5,17 | 4 | 1.148,9 |
| T4 | 29,98 | 16 | 1.665,6 |
| T8 | 2.496,79 | 256 | 8.669,4 |

Três taxas diferentes para o que deveria ser uma. O resíduo cresce ×483 de T2 a
T8 enquanto o item value cresce ×64.

Testei e descartei a hipótese de que o resíduo acumulasse a taxa dos elos
anteriores da cadeia: mesmo com retorno zero — o teto absoluto — a soma da
cadeia T2→T8 chega a **656,59**, contra 2.496,79. Está travado em
`test_a_cadeia_acumulada_nao_alcanca_o_t8_nem_com_retorno_zero`, e continua
válido como aritmética.

**O que estava errado era a premissa, não a aritmética.** Esses números nunca
foram a taxa da estação — são um resíduo de subtração sobre uma coluna agregada,
carregando tudo que a reconstrução não modelou. A planilha tem a taxa em coluna
própria, e lá ela dá 184 em 49 linhas.

Dos sete tiers prometidos só três chegaram. **Isso deixou de importar:**
recuperar os outros quatro só melhoraria uma reconstrução que agora se sabe
inválida. O item saiu da lista de pendências.

### Como medir no jogo — ainda vale, mas não é mais urgente

A medição continua sendo a única confirmação que não depende de planilha de
terceiro. O que mudou é a ordem: com anúncio oficial **e** 49 linhas de
validação independente, ela deixou de ser a prioridade 1 e passou a ser
confirmação de rotina.

**O experimento mínimo — dez minutos, uma estação só:**

1. Abrir uma estação de refino e **anotar a prata por 100 de nutrição** que ela
   anuncia. Chamar de `F`.
2. Refinar **1× T4_PLANKS** e anotar a prata debitada. Chamar de `t4`.
3. Refinar **1× T8_PLANKS** na **mesma** estação e anotar. Chamar de `t8`.

| Conferência | O que precisa dar | Se não der |
|---|---|---|
| Valor absoluto | `t4 = 16 × 0,1125 × F ÷ 100` | A constante `0,1125` ou a divisão por 100 está errada |
| Razão entre tiers | `t8 ÷ t4 = 16` (item value 256 ÷ 16) | A taxa não é proporcional ao `@itemvalue` |
| Linearidade na taxa | Repetir noutra estação com `F` diferente: a razão dos débitos precisa ser a razão dos `F` | A taxa não é linear na prata por nutrição |

**Uma quarta, se a estação permitir:** `T8_PLANKS` contra a variante encantada
nível 2 (`@itemvalue` 256 contra 1.024). A razão precisa dar **4**. A planilha
já confirma isso em `BD_Itens_Craft`, mas ali é dado de terceiro.

Bastam duas execuções, porque a fórmula é determinística — sem sorteio, sem
variação por qualidade, sem média a apurar. É o contraste com o item 6, que
exige amostragem grande por ser sorteado por unidade.

### Decisão: o campo nasce vazio, e é o único assim

**Resolvido em 19/09/2026.** `crafting.station_fee_per_100_nutrition` volta a
`NULL`/`UNKNOWN`, e a preferência do usuário nasce **vazia**. Sem ela, craft e
refino respondem desconhecido com o motivo, como qualquer parâmetro ausente.

Isso contraria a convenção do resto das preferências, que é *vir preenchido com
o aviso de que não foi verificado* (ver "Linguagem visual" no `CLAUDE.md`). A
exceção tem três razões, em ordem de peso.

**1. Nenhum dos candidatos é defensável.** Só havia dois:

| Candidato | De onde vinha | Por que não serve |
|---|---|---|
| **1.666** | mediana das taxas implicadas pelos três resíduos | Os resíduos não eram a taxa. A base desapareceu junto com a reconstrução. |
| **184** | `Crafting.Taxa da Loja` da planilha de referência | É a **escolha de estação de um jogador**, numa sessão específica. Não é constante do jogo. |

Pré-preencher qualquer um seria inventar número — a **regra 2** — e transformar
uma escolha de terceiro em padrão de produto, que é o oposto da **regra 5**
("taxa nunca é hardcode... a prata por 100 de nutrição continua sendo do
usuário").

**2. É o número mais fácil da lista inteira de obter.** Ele está **escrito na
tela da estação**, dentro do jogo. Não exige experimento, amostragem nem
comparação: exige abrir a estação e ler. Pré-preencher um valor para poupar o
usuário de um gesto de dois segundos troca precisão por conveniência no pior
câmbio possível — e ainda desestimula o único gesto que resolveria.

Compare com o item 6 (retorno de material): ali o número **não** está escrito em
lugar nenhum, exige amostragem grande por ser sorteado por unidade, e por isso
pré-preencher com procedência declarada é a escolha certa. Não é incoerência
entre os dois; é a mesma regra aplicada a dificuldades diferentes.

**3. O pré-preenchido enganava justamente onde se conferiria.** Com 1.666 a
fórmula reproduzia o resíduo do T4 quase exatamente — 29,99 contra 29,98 — por
**circularidade**, já que 1.666 saiu da mediana e a implicada pelo T4 era
1.665,6. Quem fosse conferir começaria pelo tier baixo e concluiria que fechou.
Um padrão que produz uma coincidência convincente no primeiro caso testado é
pior que nenhum padrão.

### O que a interface faz no lugar

- O campo em **Preferências** fica vazio, com `não informado` de placeholder e
  uma linha dizendo onde ler o valor no jogo.
- O **calculador** mostra `desconhecida` em âmbar ao lado do rótulo, com a
  orientação, e **184 aparece apenas como ordem de grandeza** — "costuma ficar
  na casa das centenas (a planilha de referência usava 184)". Como referência
  de magnitude, nunca como valor a copiar.
- Craft e refino respondem `known = false` com
  `crafting.station_fee_per_100_nutrition` em `missing`, que é o caminho normal
  de parâmetro ausente desde a fase 6.

O item 11 **continua** valendo como medição, e agora com um segundo motivo:
além de confirmar a fórmula sem depender de planilha de terceiro, ele é o que
destrava o cálculo para quem ainda não informou.

## Item 14 — bônus diário de produção: tentado e NÃO resolvido

> Tentado em **19/09/2026**. Fica aberto, e o registro aqui é da tentativa, não
> de uma conclusão.

O jogo sorteia um bônus diário de produção, e o dump traz `@activefarmbonus`.
A pergunta era se ele entra em `B` como mais um componente, do mesmo jeito que
os outros quatro.

**Não entra por soma.** Testado contra as colunas publicadas: o erro vai de **3
a 8 pontos percentuais**, e — o que decide — **o desvio é inconstante**. Um
erro constante sugeriria uma parcela faltando; um erro proporcional sugeriria um
fator. Um erro que varia sem padrão não sugere nenhuma das duas, e não há o que
calibrar.

Também não foi possível descartar que as colunas publicadas misturem cenários
diferentes, o que explicaria a inconstância sem que a soma esteja errada. Sem
saber disso, qualquer composição seria escolhida por caber nos números — e não
por ser a mecânica.

**Por isso o parâmetro é aceito e não aplicado.** `daily_production_bonus`
continua na assinatura das rotas e volta como `0` na resposta, para a tela poder
dizer que ele foi ignorado em vez de ele sumir sem explicação. Antes da fase 20
ele era **somado à célula da matriz**, declarado como suposição; a evidência
acima mostra que a suposição estava errada, e aplicar uma composição que se sabe
errada é pior que não aplicar nenhuma.

O que destravaria: as colunas publicadas com o cenário de cada uma (cidade,
Focus, atividade), ou uma medição direta — dois dias seguidos com o mesmo item,
mesmo local e bônus diário diferente.

### Bug corrigido de carona

`resolve_base_name` prefere a raiz sem `_LEVELN` — `T8_LEATHER_LEVEL2` vira
`T8_LEATHER`. Isso está certo para peso, tier e categoria, **idênticos** entre as
variantes, e por isso nunca incomodou. Mas `@itemvalue` **não** é idêntico: 256
contra 1.024. Na primeira importação todo item encantado saiu com o valor da
base, e a taxa da estação de um T8 encantado nível 4 saía **16× menor** que a
real. `normalize` agora busca `@itemvalue` na entrada literal antes de cair na
raiz. É o mesmo tipo de armadilha da fase 7 (`T4_ROCK_LEVEL1@1`), em outro campo.
