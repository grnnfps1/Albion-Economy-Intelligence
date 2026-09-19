from pydantic import BaseModel, Field

from app.schemas.arbitrage import FeesUsed
from app.schemas.risk import RiskOut, RiskUsed


class SpecializationUsed(BaseModel):
    """A especialização em uso, e o aviso quando não há nenhuma.

    `assumes_zero_spec` não é detalhe: o custo em Focus do dump é o de quem
    nunca especializou nada, e mostrá-lo sem a ressalva faz um número de
    ninguém parecer o número do usuário.
    """

    informed: bool = False
    assumes_zero_spec: bool = True
    levels: dict[str, int] = Field(
        default_factory=dict, description="Por família de recurso — a unidade do refino."
    )
    item_levels: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Por linha de item — a unidade do craft de equipamento. Vence a "
            "família, porque é mais específico."
        ),
    )
    families: list[str] = Field(default_factory=list)
    halving_points: float = 10_000.0
    per_mastery_level: float = 30.0
    per_spec_level: dict[str, float] = Field(default_factory=dict)


class CraftParamsUsed(BaseModel):
    """Os parâmetros que produziram estes números.

    Vão na resposta porque nenhum deles é fato fixo: retorno muda com Focus e
    especialização, taxa de estação muda por cidade e por hora, imposto muda com
    Premium. Sem isso, um lucro de 18% não é auditável.
    """

    return_rate: float | None = None
    station_fee_per_100_nutrition: float | None = Field(
        default=None,
        description=(
            "Prata por 100 de nutrição cobrada pela estação. É o número que o "
            "jogador lê na tela da estação; a taxa de cada item sai dele."
        ),
    )
    nutrition_per_item_value: float | None = Field(
        default=None,
        description="Nutrição consumida por unidade de item value. Constante do jogo.",
    )
    use_focus: bool = False
    daily_production_bonus: float = 0.0
    return_rate_source: str = "UNKNOWN"
    specialization: SpecializationUsed = Field(default_factory=SpecializationUsed)
    fees: FeesUsed = Field(default_factory=FeesUsed)
    complete: bool = False
    missing: list[str] = Field(default_factory=list)


class ReturnOut(BaseModel):
    """A taxa de retorno em uso e onde ela seria maior.

    A segunda metade é a pergunta que a tela não respondia: refinar ou craftar
    isto em qual cidade rende mais, e quanto muda. Sem ela, a diferença entre
    0,152 e 0,367 era invisível.
    """

    rate: float | None = None
    source: str = "UNKNOWN"
    has_city_bonus: bool = False
    use_focus: bool = False
    daily_bonus: float = 0.0
    matrix_rate: float | None = Field(
        default=None, description="A célula da matriz, antes do bônus diário e de sobrescrita."
    )

    best_city: str | None = None
    best_city_name: str | None = None
    rate_at_best_city: float | None = None
    delta: float | None = Field(
        default=None, description="Quanto o retorno sobe indo para a cidade do bônus."
    )
    is_best_city: bool = False
    mapping_known: bool = Field(
        default=True,
        description="False quando o mapeamento de bônus daquela atividade não foi levantado.",
    )


class MaterialOut(BaseModel):
    item: str
    item_name: str | None
    icon_url: str | None
    quantity: int
    unit_price: int | None
    total_price: float | None
    is_returnable: bool
    location: str | None = Field(default=None, description="Cidade onde esta compra acontece.")
    location_slug: str | None = None
    age_seconds: int | None

    # Quando a compra sai da cidade base, a resposta precisa dizer quanto o
    # desvio vale. Economia sem o número é só uma promessa.
    is_alternate_city: bool = False
    base_unit_price: int | None = Field(
        default=None, description="Preço na cidade base, para comparação."
    )
    savings_vs_base: float | None = Field(
        default=None,
        description="Economia desta linha contra a cidade base. None quando a base "
        "não tem cotação: aí não há o que comparar.",
    )


class SourcingOut(BaseModel):
    """O roteiro de compra: em quantas cidades ele cai e quanto isso rende.

    `cities_involved` é informação de primeira classe porque economia espalhada
    não é economia: 3% distribuídos por quatro cidades custam quatro viagens.
    """

    mode: str
    cities_involved: int
    cities: list[str] = Field(default_factory=list)

    cost_single_city: float | None = None
    cost_cheapest: float | None = None
    savings: float | None = None
    savings_pct: float | None = None

    # Só em COMPARAR: os dois roteiros calculados até o fim, não só o custo.
    profit_single_city: float | None = None
    profit_cheapest: float | None = None


class CraftEconomicsOut(BaseModel):
    known: bool
    reason: str | None = None
    output_quantity: int
    focus_cost: int
    base_focus_cost: float | None = Field(
        default=None,
        description="Focus antes da especialização — o `@craftingfocus` do dump.",
    )
    focus_multiplier: float | None = Field(
        default=None, description="`0,5 ^ (eficiência ÷ 10.000)`. 1,0 sem especialização."
    )
    material_cost_gross: float | None = None
    material_cost_net: float | None = None
    returned_value: float | None = None
    station_fee: float | None = None
    # A taxa deixou de ser um número avulso: estes dois dizem de onde ela saiu.
    # Sem eles, "taxa de estação: 2.496" é um número que ninguém confere.
    item_value: float | None = Field(
        default=None, description="`@itemvalue` do dump, base da nutrição."
    )
    nutrition: float | None = Field(
        default=None, description="Nutrição consumida por estas execuções."
    )
    sale_revenue_net: float | None = None
    market_fees: float | None = None
    profit: float | None = None
    margin_pct: float | None = None
    roi_pct: float | None = None
    profit_per_focus: float | None = None

    # Lucro por dia: o que torna craft comparável com fazenda. Não sai do tempo
    # de craft — craft não é limitado por tempo —, e sim do Focus do dia e do
    # que o mercado absorve. Ver `calculations/daily.py`.
    profit_per_day: float | None = None
    units_per_day: float | None = None
    daily_limiter: str = "DESCONHECIDO"
    daily_reason: str | None = Field(
        default=None, description="Por que o lucro por dia é desconhecido."
    )


class CraftOpportunityOut(BaseModel):
    item: str
    item_name: str | None
    icon_url: str | None
    tier: int | None
    enchantment: int
    recipe_variant: int
    station_category: str | None
    buy_location: str
    sell_location: str
    sell_price: int | None
    sell_age_seconds: int | None
    liquidity_units_per_day: float | None
    materials: list[MaterialOut]
    material_sourcing: SourcingOut
    risk: RiskOut
    material_return: ReturnOut
    economics: CraftEconomicsOut


class CraftingResponse(BaseModel):
    server: str
    buy_location: str
    sell_location: str
    crafts: int
    sort_by: str
    sourcing_mode: str = "CIDADE_UNICA"
    total: int
    params: CraftParamsUsed
    risk: RiskUsed
    generated_at: str
    data_source_note: str
    opportunities: list[CraftOpportunityOut]
