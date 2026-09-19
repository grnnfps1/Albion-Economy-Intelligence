# 05 — Custo de Focus: a fórmula e o que ela muda no produto

> Fonte: wiki oficial (páginas de Crafting Focus, Resource Return Rate e
> Refining), trazida para o projeto em 13/09/2026. **Não medido por nós.**
> Nada disto foi gravado em `config_parameters`. Ver `docs/04a-medicao-guiada.md`
> para o protocolo de confirmação dentro do jogo.

## Por que este documento existe

`calculations/chain.py:143` calcula `focus_unitario = receita.focus_cost / saida`,
e `receita.focus_cost` vem cru do dump do jogo. O dump traz o **custo base**, que
é o custo **a zero de especialização**.

Consequência: hoje a tela de Focus responde "quanto rende cada ponto de Focus
**para um personagem sem nenhuma especialização**". Para quem tem a árvore
subida, o custo real é uma fração disso — e como `profit_per_focus` é a ordenação
principal do produto, não é só o número absoluto que muda.

## A fórmula

O custo de Focus cai pela metade a cada **10.000 pontos de Focus Cost
Efficiency** (FCE), acumulados na Mastery e nas Especializações do Destiny Board
para aquela ação:

```
custo_de_focus = custo_base(tier, encantamento) × 2 ^ (−FCE / 10000)
```

### Três checagens independentes, todas batem

Não medimos no jogo, mas a fórmula é internamente consistente com três números
que a fonte cita separadamente — o que é um indício forte de que a forma está
certa:

| Caso citado pela fonte | FCE | Pela fórmula | Fonte diz |
|---|---|---|---|
| refino T4–T8 com tudo maximizado | 40.000 | 2⁻⁴ = 6,25% | 6,25% |
| poções e comida com tudo maximizado | 55.000 | 2⁻⁵ʼ⁵ = 2,21% | ~2,21% |
| rega de plantação, sem spec → spec 100 | 30.000 | 2⁻³ = 12,5%, de 1000 → 125 | 1000 → 125 |

Três domínios diferentes, uma fórmula só. É o tipo de coincidência que não é
coincidência.

## Custo base de refino, a 0 de especialização

Colunas por encantamento: Common = .0, Uncommon = .1, Rare = .2,
Exceptional = .3, Pristine = .4.

| Tier | .0 | .1 | .2 | .3 | .4 |
|---|---|---|---|---|---|
| T2 | 18 | — | — | — | — |
| T3 | 31 | — | — | — | — |
| T4 | 54 | 94 | 164 | 287 | 503 |
| T5 | 94 | 164 | 287 | 503 | 880 |
| T6 | 164 | 287 | 503 | 880 | 1.539 |
| T7 | 287 | 503 | 880 | 1.539 | 2.694 |
| T8 | 503 | 880 | 1.539 | 2.694 | 4.714 |

A tabela é uma progressão geométrica de razão ≈ 1,75 nas duas direções: subir um
tier custa o mesmo que subir um nível de encantamento. Note que `T5.0 = T4.1 = 94`
— a diagonal se repete, o que é uma boa asserção de teste se isto virar código.

### Pedra é exceção

Pedra (`STONE`) tem tabela própria, e o encantamento **dobra** em vez de seguir a
razão 1,75:

| Tier | .0 | .1 | .2 | .3 |
|---|---|---|---|---|
| T2 | 18 | — | — | — |
| T3 | 31 | — | — | — |
| T4 | 54 | 108 | 216 | 432 |
| T5 | 94 | 188 | 376 | 752 |
| T6 | 164 | 328 | 656 | 1.312 |
| T7 | 287 | 574 | 1.148 | 2.296 |
| T8 | 503 | 1.006 | 2.012 | 4.024 |

Tratar pedra pela tabela geral erra o custo de encantado por até 17%. Se a
tabela virar código, pedra precisa de caminho próprio e de teste nomeando a
armadilha.

## Orçamento de Focus: de onde vem o teto

- Conta com Premium gera **10.000 pontos por 24h**, passivamente.
- O acúmulo máximo é **30.000 pontos**.

Isto dá chão a um número que hoje é palpite na interface: o `focusBudget` padrão
de `preferences-shared.ts` é exatamente 10.000, que agora sabemos ser a geração
diária de uma conta Premium — e não um número escolhido a esmo. O teto de 30.000
é o limite de quem acumulou sem gastar, e é o valor máximo que faz sentido
oferecer no formulário.

## O que isto muda no produto

1. **A especialização entra em `focus_per_unit`, nunca na RRR.** A fonte é
   explícita: o que a especialização reduz é o custo de Focus. A taxa de retorno
   não muda. O modelo atual do projeto já separa as duas coisas — isto confirma
   a separação em vez de contradizê-la.

2. **A ordenação do produto muda, não só a escala.** Se a FCE fosse única para
   tudo, dividir todo mundo pelo mesmo fator não mexeria no ranking. Mas a FCE é
   acumulada **por linha de habilidade**: quem maximizou refino de couro e não
   tocou em minério tem custo 16× menor num e 1× no outro. O ranking de
   `profit_per_focus` de um personagem real é diferente do ranking a spec zero —
   que é o único que a plataforma sabe mostrar hoje.

3. **A FCE é entrada do usuário**, pelo mesmo motivo das taxas: depende da conta.
   Precedência igual à das taxas — parâmetro da requisição → `config_parameters`
   → UNKNOWN. O que **não** pode acontecer é assumir spec zero em silêncio, que é
   o comportamento atual.

## O que ainda falta

- **Confirmar no jogo** pela medição 9 de `docs/04a-medicao-guiada.md`: dois
  níveis de especialização no mesmo item, comparando custo de Focus por craft.
  Duas medições bastam para validar a curva, porque a fórmula é determinística.
- **Tabela de poções e comida**: veio na fonte, mas o texto colado perdeu os
  rótulos das linhas — sobraram os números sem o nome da poção. Inutilizável como
  está. Precisa ser recuperada com os nomes antes de virar qualquer coisa.
- **De onde sai a FCE do usuário**: o Destiny Board não é exposto por API
  pública conhecida. Provavelmente é entrada manual, como as taxas.

## Fora de escopo por enquanto

A mesma fonte traz dados extensos de **farming e criação de animais** (rendimento
por semente, dieta, tempo de crescimento, cidade com bônus de +10%). Nada disso
tem consumidor no produto atual: não há tela de farming, e o catálogo não modela
plantio. Fica registrado aqui que o dado existe e onde buscar, mas colocá-lo no
repositório agora seria carregar tabela grande para uma funcionalidade que não
existe. Se farming virar fase, este é o ponto de partida.

---

## Implementado na fase 16 — o que mudou em relação a este documento

> 19/09/2026. O que estava aqui como pesquisa virou código. Três pontos deste
> documento foram **conferidos contra o dump** e dois deles precisaram de
> correção.

### A fórmula ficou como estava escrita

```
eficiencia = nivel_spec × fce_por_nivel + (mastery + mastery2) × 30
focus      = focus_base × 0,5 ^ (eficiencia ÷ 10.000)
```

Vive em `calculations/specialization.py`, pura. Os pontos por nível de spec e o
`30` da maestria estão em `config_parameters` com procedência
(migration `0009_especializacao`).

O que este documento não tinha: **quantos pontos vale um nível de spec**. São
250 "únicos" para o próprio item mais 30 "mútuos" para os irmãos do mesmo nó —
e é isso que explica a tabela por tipo de peça da planilha do Albion VIP, que
parecia arbitrária:

| Tipo | Pontos por nível | Leitura |
|---|---|---|
| MAIN, 2H, GATHERER, FOOD, Refino | 250 | só os únicos |
| OFF (primário) | 250 | só os únicos |
| OFF (secundário) | 90 | três irmãos × 30, sem os únicos |
| BAG | 310 | 250 + dois irmãos × 30 |
| CAPE | 370 | 250 + quatro irmãos × 30 |

Ou seja: a coluna que o briefing chamou de "custo base de Focus por tipo de
peça" **não é custo base**. É pontos de eficiência por nível de spec. O custo
base vem do dump.

### Correção 1 — a tabela de custo base não precisa virar código

Este documento traz a tabela de custo base por tier e encantamento e sugere
transcrevê-la. **Não é necessário:** o dump já a traz item a item, em
`craftingrequirements.@craftingfocus`, e os números batem exatamente.

Conferido em 19/09/2026 contra `ao-data/ao-bin-dumps`:

```
T4_PLANKS  → 54    T4_PLANKS_LEVEL1 → 94    _LEVEL2 → 164   _LEVEL3 → 287   _LEVEL4 → 503
T8_LEATHER → 503   T8_LEATHER_LEVEL1 → 880  _LEVEL2 → 1539  _LEVEL3 → 2694  _LEVEL4 → 4714
```

São as duas linhas da tabela deste documento, valor por valor, incluindo a
diagonal `T5.0 = T4.1 = 94`. Transcrever a tabela criaria uma segunda cópia para
manter em sincronia com o dump a cada patch.

### Correção 2 — "pedra é exceção" não tem consumidor

Este documento avisa que a pedra tem tabela própria, com o encantamento
dobrando em vez de seguir a razão 1,75, e que tratá-la pela tabela geral erraria
por até 17%.

**A armadilha não existe no refino.** Conferido no dump: `STONEBLOCK` tem
**zero** variantes encantadas, contra 20 em cada uma das outras quatro famílias.

```
PLANKS      20 variantes encantadas com receita
CLOTH       20
LEATHER     20
METALBAR    20
STONEBLOCK   0
```

`T4_STONEBLOCK_LEVEL1` simplesmente não está no dump. Bloco de pedra não é
encantado — o que é encantado é a pedra bruta (`T4_ROCK_LEVEL1` existe). Como o
custo de Focus vem do dump por item, e o item não existe, não há caminho para
errar. O aviso fica registrado para o caso de a Sandbox acrescentar a linha.

### Divergência deliberada — spec ausente é zero, não UNKNOWN

O item 3 de "O que isto muda no produto" dizia que a precedência seria a das
taxas (requisição → `config_parameters` → UNKNOWN) e que assumir spec zero em
silêncio era o problema a resolver.

A fase 16 resolveu de outro jeito, seguindo o precedente do **risco de rota**
(fase 13) e não o das taxas:

- **spec ausente vale zero**, e o custo em Focus sai idêntico ao do dump;
- a resposta carrega `specialization.assumes_zero_spec = true` e a tela diz
  isso.

O que estava errado antes não era o zero — era o **silêncio**. Travar todas as
telas em UNKNOWN por um número que só o usuário tem esconderia o produto de
quem ainda não configurou nada, exatamente como travar por risco de rota
esconderia. Taxa ausente continua UNKNOWN, porque calcular sem imposto inventa
lucro; spec ausente não inventa nada, apenas superestima o Focus gasto, que é o
lado conservador.

### Granularidade: por família, não por item

A planilha faz item a item. A interface pede **cinco números** — couro, tecido,
tábuas, barras, blocos —, que é a linha de recurso inteira. Quem especializa
couro especializa a linha; centenas de campos no formulário para a exceção não
se pagam.

Craft de equipamento continua calculando com spec 0: a tabela de pontos por tipo
de peça está gravada com procedência, mas nenhuma preferência a alimenta ainda.
Errar para mais no Focus é o lado conservador.

### O que continua faltando

- A medição 9 de `docs/04a-medicao-guiada.md` segue valendo: dois níveis de
  spec no mesmo item, comparando o Focus por craft. Duas medições bastam.
- A FCE real do usuário continua sem API: o Destiny Board não é exposto. Entrada
  manual é o caminho, e é o que a fase 16 fez.
