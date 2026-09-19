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

from app.calculations.fees import FeeProfile, Strategy
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
    production_cost: float | None = None
    """Material líquido + taxa da estação + taxas de mercado.

    Existe como campo, e não como soma dos três na chamada, porque somar os
    **arredondados** faz a razão `lucro ÷ custo` variar com a quantidade: cada
    parcela carrega até meio centavo de erro, e a razão deixa de ser invariante.
    Aqui a soma é feita antes de qualquer arredondamento.
    """

    profit: float | None = None
    margin_pct: float | None = None
    margin_on_cost_pct: float | None = None
    """Lucro ÷ custo de produção — a definição que a planilha chama de margem.

    Diferente de `roi_pct`, cujo denominador é o capital imobilizado (material
    **bruto** + taxa da estação) e não inclui as taxas de mercado.
    """

    roi_pct: float | None = None
    profit_per_focus: float | None = None

    missing: list[str] = field(default_factory=list)
    """Parâmetros de configuração que faltam — coisa que o usuário preenche."""

    missing_data: list[str] = field(default_factory=list)
    """Dado de mercado que falta — coisa que o usuário **não** pode preencher.

    Separado de `missing` porque a tela precisa distinguir os dois: um pede uma
    ação ("informe a taxa da estação"), o outro pede paciência ou outra cidade.
    Uma lista só transformaria as duas coisas na mesma frase.
    """


def _unknown(
    reason: str,
    missing: list[str],
    focus: FocusCost,
    output: int,
    missing_data: list[str] | None = None,
) -> CraftEconomics:
    return CraftEconomics(
        known=False, reason=reason, missing=missing,
        missing_data=list(missing_data or []),
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

    ## `crafts` escala tudo que é extensivo, e nada que é razão

    Custo, taxa da estação, receita, lucro, focus e investimento são
    **extensivos**: dobram quando `crafts` dobra. Margem, ROI e prata por focus
    são **razões** entre dois extensivos e por isso não mudam — `crafts` se
    cancela. Há teste comparando `crafts=1` com `crafts=10_000` e exigindo que
    as três fiquem idênticas; se variarem, é arredondamento aplicado cedo
    demais, e o lugar onde isso já aconteceu foi o custo de produção (ver
    `production_cost`).

    **A taxa da estação é por execução**, não fixa da sessão: quem faz 500
    crafts paga 500 vezes. Ela consome nutrição da estação, e a nutrição é
    consumida por craft.
    """
    faltando: list[str] = []
    # Aceita o número cru para quem não modela especialização; internamente
    # sempre é um `FocusCost`, para que base e multiplicador cheguem à resposta.
    if not isinstance(focus_cost, FocusCost):
        focus_cost = focus_cost_with_spec(float(focus_cost), SpecProfile())

    if not materials:
        return _unknown("receita sem materiais", faltando, focus_cost, output_quantity)

    # ------------------------------------------------------------------ #
    # Os impedimentos são colhidos **todos** antes de responder.
    #
    # Antes isto era uma sequência de returns: o primeiro impedimento
    # encontrado virava a resposta e os outros ficavam invisíveis. Uma linha
    # sem cotação do material **e** sem preço de venda dizia só a primeira
    # coisa, e quem a consertasse descobriria a segunda só na tentativa
    # seguinte. Numa tela em que o impedimento é o único conteúdo da linha,
    # dizer metade é pior que dizer nada — dá a impressão de que falta um
    # passo quando faltam dois.
    #
    # `missing` continua sendo só a lista de **parâmetros** de configuração,
    # porque quem a consome (a tira do topo) fala de configuração. O que falta
    # de **dado** vai em `missing_data`: a diferença importa para a tela, que
    # precisa separar "preencha um campo" de "o mercado não tem cotação".
    # ------------------------------------------------------------------ #
    sem_dado: list[str] = []

    # Nome visual **e** id técnico: a tela mostra o nome para quem lê, e o id
    # continua na frase para quem procura no dump ou abre um chamado. Só o id
    # seria ilegível; só o nome deixaria a linha sem como ser rastreada.
    sem_preco = [
        f"{m.display_name} ({m.unique_name})" if m.display_name else m.unique_name
        for m in materials
        if not m.known
    ]
    if sem_preco:
        sem_dado.append(f"sem cotação de {', '.join(sem_preco[:3])}")

    if sell_price is None or sell_price <= 0:
        sem_dado.append("sem cotação de venda do item final")

    if return_rate is None:
        faltando.append("crafting.return_rate")
    if not station_fee.known:
        faltando.append("crafting.station_fee_per_100_nutrition")
    if not fees.complete:
        faltando.extend(fees.missing())

    if faltando or sem_dado:
        partes = list(sem_dado)
        if faltando:
            partes.append("parâmetros não configurados: " + ", ".join(faltando))
        return _unknown(
            "; ".join(partes), faltando, focus_cost, output_quantity, missing_data=sem_dado
        )

    # ------------------------------------------------------------------ #
    # Tudo por **uma execução** primeiro; `crafts` multiplica no fim.
    #
    # A ordem importa, e não é preferência de estilo. As razões — margem, ROI,
    # prata por focus — saem dos valores por execução, onde `crafts` nunca
    # entrou. Calculá-las a partir dos totais daria o mesmo número em
    # matemática exata e **não** em ponto flutuante: `(a·N − b·N)/(c·N)` e
    # `(a−b)/c` diferem no último bit, e quando o valor cai perto de x,xx5 o
    # arredondamento a duas casas vira para lados diferentes. Uma margem que
    # muda de 8,57% para 8,58% ao trocar a quantidade não parece bug — parece
    # ganho de escala, que é pior.
    #
    # A taxa de venda também é unitária e exata. Antes ela vinha de
    # `compute_trade`, que arredonda a taxa **total** a duas casas e foi escrito
    # para arbitragem: cobrava setup fee nas duas pontas, e o item craftado não
    # tem ordem de compra — ele sai da estação. Os dois problemas saíram junto.
    # ------------------------------------------------------------------ #
    custo_bruto_1 = sum(m.gross_cost or 0 for m in materials)
    # Só o que é elegível retorna.
    base_retorno_1 = sum((m.gross_cost or 0) for m in materials if m.is_returnable)
    valor_retornado_1 = base_retorno_1 * (return_rate or 0.0)
    custo_liquido_1 = custo_bruto_1 - valor_retornado_1
    # `station_fee` já vem para uma execução: a estação cobra por craft, não por
    # sessão. Quem faz 500 paga 500 vezes.
    taxa_estacao_1 = station_fee.silver or 0.0

    setup = (fees.setup_fee_pct or 0.0) if strategy is Strategy.PATIENT else 0.0
    taxa_de_venda_unitaria = sell_price * ((fees.sales_tax_pct or 0.0) + setup)
    taxas_mercado_1 = taxa_de_venda_unitaria * output_quantity
    receita_liquida_1 = (sell_price - taxa_de_venda_unitaria) * output_quantity

    lucro_1 = receita_liquida_1 - custo_liquido_1 - taxa_estacao_1
    custo_producao_1 = custo_liquido_1 + taxa_estacao_1 + taxas_mercado_1
    investimento_1 = custo_bruto_1 + taxa_estacao_1
    receita_bruta_1 = float(sell_price) * output_quantity
    focus_1 = focus_cost.focus

    unidades = output_quantity * crafts
    custo_bruto = custo_bruto_1 * crafts
    valor_retornado = valor_retornado_1 * crafts
    custo_liquido = custo_liquido_1 * crafts
    taxa_estacao = taxa_estacao_1 * crafts
    taxas_mercado = taxas_mercado_1 * crafts
    receita_liquida = receita_liquida_1 * crafts
    lucro = lucro_1 * crafts
    custo_producao = custo_producao_1 * crafts
    focus_total = focus_1 * crafts

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
        production_cost=round(custo_producao, 2),
        profit=round(lucro, 2),
        # As razões vêm dos valores por execução — ver o comentário acima.
        margin_pct=round(lucro_1 / receita_bruta_1 * 100, 2) if receita_bruta_1 else None,
        margin_on_cost_pct=(
            round(lucro_1 / custo_producao_1 * 100, 2) if custo_producao_1 else None
        ),
        roi_pct=round(lucro_1 / investimento_1 * 100, 2) if investimento_1 else None,
        # A métrica que ordena o ranking da fase 9: Focus é o recurso escasso,
        # não a prata. Lucro absoluto alto com Focus alto pode ser pior negócio.
        profit_per_focus=round(lucro_1 / focus_1, 2) if focus_1 > 0 else None,
    )
