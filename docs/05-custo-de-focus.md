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
