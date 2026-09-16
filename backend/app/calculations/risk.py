"""Risco de rota: o que a zona custa antes de o lucro existir.

Funções puras, como o resto de `calculations/`.

O que este módulo conserta: uma rota que atravessa zona vermelha paga mais
**porque pode custar a carga inteira**. Mostrar só o lucro bruto de uma rota
dessas ao lado do lucro bruto de uma rota azul é comparar duas coisas que não
são comparáveis — e é exatamente a recomendação que quebra o jogador, porque a
rota perigosa sempre parece melhor.

A conta é uma só:

    esperado = lucro × (1 − p) − investimento × p

Ou seja: na fração `1 − p` das viagens você leva o lucro; na fração `p` você
perde a carga, e perder a carga não é "ganhar zero" — é perder o que investiu
nela. Tratar a perda como lucro zero subestima o dano pela metade ou mais.

`p` é **preferência do usuário**, como as taxas, e o padrão é **zero**. Zero
aqui não é chute disfarçado: é dizer "não estou modelando perda", e o resultado
ajustado fica idêntico ao bruto, visivelmente. Quem quiser modelar informa o
número que a própria experiência mostra.
"""

from dataclasses import dataclass
from enum import StrEnum


class Zone(StrEnum):
    LOCAL = "MESMA_CIDADE"
    """Origem e destino são o mesmo mercado: não há viagem e não há perda."""

    BLUE = "AZUL"
    """Cidade real ↔ cidade real. Não é livre de risco, mas não é PvP aberto."""

    RED_BLACK = "VERMELHA_PRETA"
    """Qualquer ponta em Caerleon ou no Black Market: atravessa zona aberta."""


# Quanto cada zona "custa" em distância, de 0 (pior) a 1 (melhor), para o
# componente `distance` do score. São opinião do produto, não fato do jogo — por
# isso ficam aqui como padrão e podem ser sobrescritas por configuração, do
# mesmo jeito que as referências de normalização do score.
DEFAULT_DISTANCE_FACTORS = {
    Zone.LOCAL: 1.0,
    Zone.BLUE: 0.6,
    Zone.RED_BLACK: 0.2,
}


@dataclass(frozen=True)
class RiskProfile:
    """Probabilidade de perder a carga, por zona. Preferência do usuário.

    Duas casas e não uma porque o risco de uma rota entre cidades reais e o de
    uma rota que passa por Caerleon não são o mesmo número, e forçar um valor
    único obrigaria o usuário a errar um dos dois.
    """

    loss_pct_blue: float = 0.0
    loss_pct_red_black: float = 0.0

    def probability(self, zone: Zone) -> float:
        if zone is Zone.LOCAL:
            # Sem viagem não há emboscada. Não é otimismo: é a ausência do
            # evento que se está modelando.
            return 0.0
        if zone is Zone.BLUE:
            return _clamp(self.loss_pct_blue)
        return _clamp(self.loss_pct_red_black)

    @property
    def modelled(self) -> bool:
        """O usuário informou algum risco, ou está tudo em zero?"""
        return self.loss_pct_blue > 0 or self.loss_pct_red_black > 0


@dataclass(frozen=True)
class RiskAdjusted:
    """Os dois números lado a lado. Nunca só o ajustado, nunca só o bruto.

    Só o bruto esconde o risco. Só o ajustado esconde de onde o desconto veio —
    e um número que já vem descontado, sem o original ao lado, não é auditável.
    """

    zone: str
    loss_probability: float
    gross_profit: float | None = None
    investment: float | None = None
    expected_profit: float | None = None
    expected_loss: float | None = None
    """Quanto o risco tirou do lucro bruto. É `gross - expected`."""

    @property
    def known(self) -> bool:
        return self.expected_profit is not None

    @property
    def survives_risk(self) -> bool:
        """A operação continua valendo depois do desconto?

        Uma rota pode ser lucrativa no bruto e negativa no ajustado. É o caso
        que esta fase existe para tornar visível.
        """
        return self.expected_profit is not None and self.expected_profit > 0


def _clamp(value: float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, value))


def classify_zone(origin_slug: str, destination_slug: str, open_world: frozenset[str]) -> Zone:
    """Zona de um par origem-destino.

    `open_world` chega como argumento em vez de estar escrito aqui: quais locais
    ficam em zona aberta é dado de referência (`locations`), não regra de
    cálculo. Hoje são Caerleon e o Black Market.
    """
    if origin_slug == destination_slug:
        return Zone.LOCAL
    if origin_slug in open_world or destination_slug in open_world:
        return Zone.RED_BLACK
    return Zone.BLUE


def adjust_for_risk(
    profit: float | None,
    investment: float | None,
    zone: Zone,
    profile: RiskProfile,
) -> RiskAdjusted:
    """Lucro esperado de uma operação que pode não chegar ao destino.

        esperado = lucro × (1 − p) − investimento × p

    O segundo termo é o que quase toda calculadora esquece. Sem ele, perder a
    carga valeria zero, e uma rota com 20% de perda pareceria render 80% do
    lucro — quando na verdade ela também queima 20% do capital investido.
    """
    p = profile.probability(zone)

    if profit is None or investment is None:
        return RiskAdjusted(zone=str(zone), loss_probability=p)

    esperado = profit * (1 - p) - investment * p

    return RiskAdjusted(
        zone=str(zone),
        loss_probability=round(p, 4),
        gross_profit=round(profit, 2),
        investment=round(investment, 2),
        expected_profit=round(esperado, 2),
        expected_loss=round(profit - esperado, 2),
    )


def distance_factor(zone: Zone, factors: dict[Zone, float] | None = None) -> float:
    """Fator 0–1 que alimenta o componente `distance` do score."""
    tabela = factors or DEFAULT_DISTANCE_FACTORS
    return tabela.get(zone, DEFAULT_DISTANCE_FACTORS[Zone.RED_BLACK])
