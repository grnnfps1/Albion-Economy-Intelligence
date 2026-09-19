"""Taxa da estação de crafting: derivada do valor do item, não fixa.

Até a fase 14 a taxa da estação era um número fixo de prata por execução
(`crafting.station_fee`, padrão 100). Isso está errado, e o erro cresce com o
tier: reconstruindo o refino de couro, o resíduo depois de materiais e retorno
vai de 5,17 no T2 a 2.496,79 no T8. Um valor único erra por duas ordens de
grandeza nas pontas.

## A mecânica

O jogo não cobra por execução: cobra por **nutrição consumida**. Quem anunciou a
mudança foi a própria Sandbox, no patch Lands Awakened:

    "Usage Fees are now derived directly from the Nutrition an Item consumes
     when it is crafted/studied at a building"
    "Nutrition Cost = Item Value * 0.1125"
    "Usage Fees are now set as an amount of Silver per 100 Nutrition consumed"

Logo:

    nutricao   = item_value × 0,1125
    taxa       = nutricao × (prata_por_100_nutricao ÷ 100)

`item_value` é `@itemvalue` no dump do cliente, e está lá para 2.398 itens --
entre eles **todos** os recursos refinados. Ele dobra a cada tier e a cada nível
de encantamento (`T2_LEATHER` = 4 … `T8_LEATHER` = 256; `T8_LEATHER_LEVEL4` =
4.096), que é exatamente o eixo em que a taxa escala.

## O que o usuário informa

`prata_por_100_nutricao` é o número que o dono da estação anuncia e que o
jogador lê na tela da estação. É **dele**, não do sistema -- muda por cidade,
por estação e por hora -- e por isso chega aqui como argumento obrigatório, pela
mesma razão que `FeeProfile` chega em `fees.py`. Nenhuma função deste módulo lê
configuração.

## O que não fechou

Os três resíduos reconstruídos da planilha **não** são reproduzíveis por uma
taxa única: cada um implica um `prata_por_100_nutrição` diferente.

    tier | resíduo   | item value | prata/100 nutrição implicada
    -----|-----------|------------|-----------------------------
    T2   |     5,17  |          4 |                     1.148,9
    T4   |    29,98  |         16 |                     1.665,6
    T8   | 2.496,79  |        256 |                     8.669,4

Isso é *consistente* com a mecânica -- cada estação cobra o que quer -- mas
significa que os resíduos não validam a fórmula: a taxa cresce ×64 de T2 a T8
(é o que o item value faz) enquanto o resíduo cresce ×483. A hipótese de que o
resíduo acumula a taxa dos elos anteriores da cadeia foi testada e **descartada**
por aritmética: mesmo com retorno zero, a soma da cadeia T2→T8 chega a 656,59,
contra os 2.496,79 observados. Ver `docs/04-taxas.md` §11.

A fórmula fica porque tem fonte oficial, não porque a planilha a confirmou.
"""

from dataclasses import dataclass

# Constante da Sandbox, anunciada no Lands Awakened. Não é estimativa da
# comunidade nem chute: é o número do anúncio de patch.
NUTRITION_PER_ITEM_VALUE = 0.1125

FONTE_NUTRICAO = (
    "Sandbox Interactive, anuncio do patch Lands Awakened (2021): "
    "'Nutrition Cost = Item Value * 0.1125'; consultado em 19/09/2026"
)


@dataclass(frozen=True)
class StationFee:
    """Taxa de estação de uma execução. `silver=None` é UNKNOWN, nunca zero."""

    silver: float | None
    item_value: float | None = None
    nutrition: float | None = None
    fee_per_100_nutrition: float | None = None
    reason: str | None = None
    """Por que é UNKNOWN. Sem isto o usuário não sabe o que preencher."""

    @property
    def known(self) -> bool:
        return self.silver is not None


def nutrition_for(item_value: float | None) -> float | None:
    """Nutrição consumida por uma execução que produz um item de `item_value`.

    `None` entra e `None` sai: item sem `@itemvalue` no dump não vira nutrição
    zero. Dos 455 itens rastreados, 97 não têm o campo -- são animais de pasto e
    ferramentas de rastreamento, que não passam por estação de crafting. Chutar
    zero ali produziria taxa zero e lucro inflado.
    """
    if item_value is None or item_value < 0:
        return None
    return item_value * NUTRITION_PER_ITEM_VALUE


def station_fee_for(
    item_value: float | None,
    fee_per_100_nutrition: float | None,
    crafts: int = 1,
) -> StationFee:
    """Prata paga à estação por `crafts` execuções.

    Os dois argumentos são obrigatórios no sentido que importa: qualquer um
    ausente devolve UNKNOWN com o motivo. Não existe "taxa zero por omissão" --
    é a regra 2 do CLAUDE.md, e aqui ela morde com força, porque uma taxa de
    estação esquecida no T8 é 2.500 de prata por unidade que some do custo.
    """
    if crafts <= 0:
        return StationFee(silver=None, reason="número de execuções precisa ser positivo")

    nutricao = nutrition_for(item_value)
    if nutricao is None:
        return StationFee(
            silver=None,
            item_value=item_value,
            fee_per_100_nutrition=fee_per_100_nutrition,
            reason="item sem @itemvalue no dump: nutrição desconhecida",
        )

    if fee_per_100_nutrition is None:
        return StationFee(
            silver=None,
            item_value=item_value,
            nutrition=round(nutricao, 4),
            reason="taxa da estação não informada: crafting.station_fee_per_100_nutrition",
        )

    if fee_per_100_nutrition < 0:
        return StationFee(
            silver=None,
            item_value=item_value,
            nutrition=round(nutricao, 4),
            fee_per_100_nutrition=fee_per_100_nutrition,
            reason="taxa da estação negativa",
        )

    return StationFee(
        silver=round(nutricao * fee_per_100_nutrition / 100.0 * crafts, 4),
        item_value=item_value,
        nutrition=round(nutricao * crafts, 4),
        fee_per_100_nutrition=fee_per_100_nutrition,
    )
