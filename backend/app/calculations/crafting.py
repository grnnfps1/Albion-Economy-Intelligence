"""Economia de um craft.

Funções puras. Como em `fees.py`, todo parâmetro de jogo chega como argumento e
ausência vira `UNKNOWN` — nunca zero.

Três parâmetros que o usuário precisa informar e que **não** são fatos fixos:

- **taxa de retorno de material**: muda com Focus, com a especialização da
  estação e com o bônus da cidade;
- **especialização**: o `@craftingfocus` do dump é o custo de quem nunca
  especializou nada (`calculations/specialization.py`);
- **taxa da estação**: o dono define a prata por 100 de nutrição, e a nutrição
  consumida sai do valor do item — por isso a taxa escala com tier e
  encantamento (`calculations/station.py`);
- **imposto de venda**: muda com Premium.

Uma calculadora que fixa esses três está errada para quase todo mundo.
"""

from dataclasses import dataclass, field

from app.calculations.fees import FeeProfile, Strategy, compute_trade
from app.calculations.specialization import FocusCost, SpecProfile, focus_cost_with_spec
from app.calculations.station import StationFee


@dataclass(frozen=True)
class MaterialCost:
    unique_name: str
    display_name: str | None
    quantity: int
    unit_price: int | None
    is_returnable: bool
    location: str | None = None
    age_seconds: int | None = None

    @property
    def known(self) -> bool:
        return self.unit_price is not None

    @property
    def gross_cost(self) -> float | None:
        return None if self.unit_price is None else self.unit_price * self.quantity


@dataclass(frozen=True)
class CraftEconomics:
    known: bool
    reason: str | None = None
    output_quantity: int = 1
    focus_cost: float = 0.0
    base_focus_cost: float | None = None
    focus_multiplier: float | None = None
    material_cost_gross: float | None = None
    material_cost_net: float | None = None
    returned_value: float | None = None
    station_fee: float | None = None
    item_value: float | None = None
    nutrition: float | None = None
    sale_revenue_net: float | None = None
    market_fees: float | None = None
    profit: float | None = None
    margin_pct: float | None = None
    roi_pct: float | None = None
    profit_per_focus: float | None = None
    missing: list[str] = field(default_factory=list)


def _unknown(reason: str, missing: list[str], focus: FocusCost, output: int) -> CraftEconomics:
    return CraftEconomics(
        known=False, reason=reason, missing=missing,
        focus_cost=focus.focus, base_focus_cost=focus.base_focus,
        focus_multiplier=focus.multiplier, output_quantity=output,
    )


def compute_craft(
    materials: list[MaterialCost],
    sell_price: int | None,
    fees: FeeProfile,
    return_rate: float | None,
    station_fee: StationFee,
    output_quantity: int = 1,
    focus_cost: FocusCost | float = 0.0,
    crafts: int = 1,
    strategy: Strategy = Strategy.FAST,
) -> CraftEconomics:
    """Lucro de `crafts` execuções da receita.

    O retorno de material devolve **recurso**, não prata. Aqui ele é convertido
    a preço de mercado, porque é assim que o jogador realiza o valor: revendendo
    ou reaproveitando no craft seguinte. Materiais não elegíveis ficam fora da
    conta — tratar todos igual infla o lucro.
    """
    faltando: list[str] = []
    # Aceita o número cru para quem não modela especialização; internamente
    # sempre é um `FocusCost`, para que base e multiplicador cheguem à resposta.
    if not isinstance(focus_cost, FocusCost):
        focus_cost = focus_cost_with_spec(float(focus_cost), SpecProfile())

    if not materials:
        return _unknown("receita sem materiais", faltando, focus_cost, output_quantity)

    sem_preco = [m.unique_name for m in materials if not m.known]
    if sem_preco:
        return _unknown(
            f"sem cotação para {len(sem_preco)} material(is): {', '.join(sem_preco[:3])}",
            faltando,
            focus_cost,
            output_quantity,
        )

    if return_rate is None:
        faltando.append("crafting.return_rate")
    if not station_fee.known:
        faltando.append("crafting.station_fee_per_100_nutrition")
    if not fees.complete:
        faltando.extend(fees.missing())

    if faltando:
        return _unknown(
            "parâmetros não configurados: " + ", ".join(faltando),
            faltando,
            focus_cost,
            output_quantity,
        )

    if sell_price is None or sell_price <= 0:
        return _unknown("sem cotação de venda do item final", faltando, focus_cost, output_quantity)

    custo_bruto = sum(m.gross_cost or 0 for m in materials) * crafts
    # Só o que é elegível retorna.
    base_retorno = sum((m.gross_cost or 0) for m in materials if m.is_returnable) * crafts
    valor_retornado = base_retorno * (return_rate or 0.0)
    custo_liquido = custo_bruto - valor_retornado
    # `station_fee` já vem para uma execução; aqui só escala.
    taxa_estacao = (station_fee.silver or 0.0) * crafts

    unidades = output_quantity * crafts
    venda = compute_trade(
        buy_price=1,  # o custo real entra por fora; aqui só interessam as taxas de venda
        sell_price=sell_price,
        fees=fees,
        strategy=strategy,
        quantity=unidades,
    )
    receita_liquida = (venda.unit_revenue or 0.0) * unidades
    # `compute_trade` cobra setup fee **das duas pontas**, porque foi escrito
    # para arbitragem: lá se cria ordem de compra e ordem de venda. Em craft não
    # há ordem de compra do item produzido — ele sai da estação —, então o setup
    # do lado da compra é fantasma. Com o `buy_price=1` sentinela ele é pequeno
    # (2,5 de prata em 100 unidades), mas faz a taxa de venda deixar de ser
    # exatamente o percentual anunciado, e num calculador isso corrói confiança.
    setup_fantasma = (fees.setup_fee_pct or 0.0) * unidades if strategy is Strategy.PATIENT else 0.0
    taxas_mercado = max(0.0, (venda.fees or 0.0) - setup_fantasma)

    lucro = receita_liquida - custo_liquido - taxa_estacao
    investimento = custo_bruto + taxa_estacao
    receita_bruta = float(sell_price) * unidades
    focus_total = focus_cost.focus * crafts

    return CraftEconomics(
        known=True,
        output_quantity=unidades,
        focus_cost=round(focus_total, 4),
        base_focus_cost=round(focus_cost.base_focus * crafts, 4),
        focus_multiplier=focus_cost.multiplier,
        material_cost_gross=round(custo_bruto, 2),
        material_cost_net=round(custo_liquido, 2),
        returned_value=round(valor_retornado, 2),
        station_fee=round(taxa_estacao, 2),
        item_value=station_fee.item_value,
        nutrition=(
            None if station_fee.nutrition is None
            else round(station_fee.nutrition * crafts, 4)
        ),
        sale_revenue_net=round(receita_liquida, 2),
        market_fees=round(taxas_mercado, 2),
        profit=round(lucro, 2),
        margin_pct=round(lucro / receita_bruta * 100, 2) if receita_bruta else None,
        roi_pct=round(lucro / investimento * 100, 2) if investimento else None,
        # A métrica que ordena o ranking da fase 9: Focus é o recurso escasso,
        # não a prata. Lucro absoluto alto com Focus alto pode ser pior negócio.
        profit_per_focus=round(lucro / focus_total, 2) if focus_total > 0 else None,
    )
