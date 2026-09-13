"""Economia de uma operação de mercado.

Funções puras. As taxas chegam como **argumento obrigatório** — nunca são lidas
de dentro da fórmula (requisito 26). Quem escolhe os valores é a camada de
serviço, a partir da configuração do sistema ou das preferências do usuário.

Por que as taxas são do usuário e não do sistema: o imposto de venda depende de
a conta ter Premium. Uma plataforma que assume um valor fixo mostra lucro errado
para metade das pessoas.

Regra central: **parâmetro ausente não vira zero.** Taxa faltando produz
`UNKNOWN`, porque margem calculada sem imposto é sempre otimista, e otimista
aqui significa recomendar uma operação que perde prata.
"""

from dataclasses import dataclass
from enum import StrEnum


class Strategy(StrEnum):
    """Como a operação é executada. Muda quais taxas incidem."""

    FAST = "IMEDIATA"
    """Compra das ordens de venda existentes e vende para as ordens de compra.
    Executa na hora e não paga setup fee, porque não cria ordem nenhuma."""

    PATIENT = "PACIENTE"
    """Cria ordem de compra na origem e ordem de venda no destino. Preço melhor
    nas duas pontas, mas paga setup fee duas vezes e pode não executar."""


@dataclass(frozen=True)
class FeeProfile:
    """Taxas em uso. `None` significa desconhecido, nunca zero."""

    setup_fee_pct: float | None = None
    sales_tax_pct: float | None = None
    premium: bool | None = None

    @property
    def complete(self) -> bool:
        return self.setup_fee_pct is not None and self.sales_tax_pct is not None

    def missing(self) -> list[str]:
        faltando = []
        if self.setup_fee_pct is None:
            faltando.append("market.sell_order_setup_fee_pct")
        if self.sales_tax_pct is None:
            faltando.append("market.sales_tax_pct")
        return faltando


@dataclass(frozen=True)
class TradeEconomics:
    """Resultado do cálculo. `known=False` quando falta parâmetro ou preço."""

    known: bool
    strategy: Strategy
    quantity: int
    unit_cost: float | None = None
    unit_revenue: float | None = None
    investment: float | None = None
    gross_revenue: float | None = None
    fees: float | None = None
    transport_cost: float | None = None
    net_profit: float | None = None
    margin_pct: float | None = None
    roi_pct: float | None = None
    reason: str | None = None
    """Por que é UNKNOWN. Sem isto, o usuário não sabe o que fazer para destravar."""


def _unknown(strategy: Strategy, quantity: int, reason: str) -> TradeEconomics:
    return TradeEconomics(known=False, strategy=strategy, quantity=quantity, reason=reason)


def compute_trade(
    buy_price: int | None,
    sell_price: int | None,
    fees: FeeProfile,
    strategy: Strategy,
    quantity: int = 1,
    transport_cost_per_unit: float = 0.0,
) -> TradeEconomics:
    """Economia de comprar por `buy_price` e vender por `sell_price`.

    `buy_price` é o que sai do bolso por unidade na origem; `sell_price` é o
    preço bruto de venda no destino, antes de imposto.

    Na estratégia IMEDIATA não há setup fee: você consome ordens que já existem.
    Na PACIENTE ele incide duas vezes — na ordem de compra e na de venda — e é
    pago mesmo que a ordem nunca execute. Ignorar essa diferença é o erro que
    faz uma arbitragem "de 9%" virar prejuízo.
    """
    if quantity <= 0:
        return _unknown(strategy, quantity, "quantidade precisa ser positiva")

    if buy_price is None or sell_price is None:
        return _unknown(
            strategy, quantity, "sem cotação em uma das pontas (não há ordem registrada)"
        )
    if buy_price <= 0 or sell_price <= 0:
        return _unknown(strategy, quantity, "preço não positivo")

    if not fees.complete:
        return _unknown(
            strategy,
            quantity,
            "taxas não configuradas: " + ", ".join(fees.missing()),
        )

    setup = fees.setup_fee_pct or 0.0
    imposto = fees.sales_tax_pct or 0.0

    if strategy is Strategy.FAST:
        custo_unitario = float(buy_price)
        # Vender para uma ordem de compra paga imposto, mas não cria ordem.
        receita_unitaria = sell_price * (1 - imposto)
        taxa_unitaria = sell_price * imposto
    else:
        # Criar ordem de compra custa setup fee sobre o valor ofertado.
        custo_unitario = buy_price * (1 + setup)
        receita_unitaria = sell_price * (1 - imposto - setup)
        taxa_unitaria = sell_price * (imposto + setup) + buy_price * setup

    investimento = (custo_unitario + transport_cost_per_unit) * quantity
    receita_bruta = float(sell_price) * quantity
    taxas_totais = taxa_unitaria * quantity
    transporte = transport_cost_per_unit * quantity
    lucro = (receita_unitaria - custo_unitario - transport_cost_per_unit) * quantity

    return TradeEconomics(
        known=True,
        strategy=strategy,
        quantity=quantity,
        unit_cost=round(custo_unitario + transport_cost_per_unit, 2),
        unit_revenue=round(receita_unitaria, 2),
        investment=round(investimento, 2),
        gross_revenue=round(receita_bruta, 2),
        fees=round(taxas_totais, 2),
        transport_cost=round(transporte, 2),
        net_profit=round(lucro, 2),
        # Margem sobre a receita bruta: é quanto do que entra realmente sobra.
        margin_pct=round(lucro / receita_bruta * 100, 2) if receita_bruta else None,
        # ROI sobre o capital imobilizado: é o que compara operações de tamanhos
        # diferentes. Margem alta com ROI baixo é armadilha de capital parado.
        roi_pct=round(lucro / investimento * 100, 2) if investimento else None,
    )
