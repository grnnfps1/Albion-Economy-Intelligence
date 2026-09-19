"""Resposta do calculador de crafting."""

from pydantic import BaseModel, Field

from app.schemas.arbitrage import FeesUsed
from app.schemas.crafting import ReturnOut, SpecializationUsed


class CalcMaterialOut(BaseModel):
    """Um material da linha, com preço editável e o que comprar."""

    item: str
    item_name: str | None = None
    icon_url: str | None = None
    quantity: int
    is_returnable: bool
    role: str = Field(
        default="outro",
        description=(
            "Papel do material na receita: 'bruto', 'refinado', 'token' ou "
            "'outro'. A tela usa isto para dar uma coluna fixa a cada papel, "
            "de modo que 'bruto' signifique a mesma coisa em todas as linhas."
        ),
    )

    unit_price: int | None = None
    price_is_manual: bool = False
    collected_price: int | None = Field(
        default=None, description="O que a coleta dizia, quando o manual venceu."
    )
    age_seconds: int | None = None
    location: str | None = None
    is_alternate_city: bool = False

    # Lista de compras: quanto comprar para a quantidade pedida.
    buy_units: int = 0
    gross_units: float = 0
    saved_by_return: float = 0


class CalcRowOut(BaseModel):
    """Uma combinação de tier e encantamento da família."""

    item: str
    item_name: str | None = None
    icon_url: str | None = None
    tier: int | None = None
    enchantment: int = 0
    tier_label: str = Field(description="`T4.2`, como a planilha nomeia a linha.")

    sell_price: int | None = None
    sell_price_is_manual: bool = False
    sell_collected_price: int | None = None
    sell_age_seconds: int | None = None
    liquidity_units_per_day: float | None = None

    materials: list[CalcMaterialOut] = Field(default_factory=list)

    # Qual variante da receita foi usada, e qual foi descartada.
    variant_label: str | None = None
    alternative_label: str | None = None
    alternative_cost: float | None = None

    # ---- colunas calculadas, na ordem em que a conta se constrói ----
    material_cost: float | None = Field(
        default=None, description="Materiais **já com o retorno aplicado**."
    )
    material_cost_gross: float | None = None
    returned_value: float | None = None
    station_fee: float | None = None
    sale_fee: float | None = Field(
        default=None, description="Imposto de venda + setup fee sobre a receita bruta."
    )
    production_cost: float | None = Field(
        default=None, description="Material + taxa da loja + taxa de venda."
    )
    gross_revenue: float | None = None
    profit: float | None = None
    margin_pct: float | None = Field(
        default=None, description="Lucro sobre a receita bruta — a definição do projeto."
    )
    margin_on_cost_pct: float | None = Field(
        default=None,
        description="Lucro sobre o custo de produção — a definição da planilha.",
    )

    focus_cost: float = 0
    profit_per_focus: float | None = None

    # ---- previsão para a quantidade pedida ----
    total_profit: float | None = None
    total_investment: float | None = None
    days_to_sell: float | None = None

    known: bool = False
    reason: str | None = None
    blocker: str | None = Field(
        default=None,
        description=(
            "O que impede o cálculo desta linha: 'parametro' quando falta "
            "configuração que o usuário preenche, 'cotacao' quando falta dado "
            "de mercado que ele não pode preencher, 'ambos' quando as duas "
            "coisas. A tela precisa separá-los: um pede uma ação, o outro não."
        ),
    )
    blocked_data: list[str] = Field(
        default_factory=list,
        description="O que falta de dado, em frase curta, para a linha poder dizê-lo.",
    )


class CalcParamsUsed(BaseModel):
    quantity: int
    sourcing: str
    strategy: str
    station_fee_per_100_nutrition: float | None = None
    nutrition_per_item_value: float | None = None
    focus_per_day: float | None = None
    fees: FeesUsed = Field(default_factory=FeesUsed)
    specialization: SpecializationUsed = Field(default_factory=SpecializationUsed)
    complete: bool = False
    missing: list[str] = Field(default_factory=list)


class CalculatorResponse(BaseModel):
    server: str
    family: str
    families: list[str] = Field(default_factory=list)
    buy_location: str
    sell_location: str

    rows: list[CalcRowOut] = Field(default_factory=list)
    material_return: ReturnOut = Field(default_factory=ReturnOut)
    params: CalcParamsUsed

    return_note: str = Field(
        description="A ressalva do retorno: ele só se realiza refinando em sequência."
    )
    generated_at: str
    data_source_note: str
