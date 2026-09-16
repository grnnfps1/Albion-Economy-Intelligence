"""Score de oportunidade.

Combina sinais heterogêneos num número de 0 a 100 (requisito 20). Duas
propriedades que o desenho precisa ter:

1. **Pesos configuráveis.** Eles vivem em `config_parameters` e chegam aqui como
   argumento. Calibrar o score não pode exigir deploy.
2. **Componente ausente não conta como zero.** Se a liquidez é desconhecida, o
   peso dela é redistribuído entre os componentes conhecidos e o `confidence`
   cai. Pontuar zero por falta de dado puniria item novo como se fosse ruim; e
   pontuar cheio esconderia que não se sabe.
"""

from dataclasses import dataclass, field

# Referências de normalização. São opinião do produto, não fato do jogo, e por
# isso ficam configuráveis junto com os pesos.
DEFAULT_REFERENCES = {
    "profit_silver": 500_000.0,   # lucro que já é "excelente" numa operação
    "margin_pct": 20.0,
    "roi_pct": 25.0,
    "liquidity_units_per_day": 500.0,
    "freshness_seconds": 21_600.0,  # 6 h: acima disso o frescor vale ~0
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass
class ScoreInputs:
    """Cada campo é `None` quando o sinal não existe. Nunca preencher com zero."""

    profit: float | None = None
    margin_pct: float | None = None
    roi_pct: float | None = None
    freshness_seconds: int | None = None
    liquidity_units_per_day: float | None = None
    trend_pct: float | None = None

    # Os dois pesos que existiam em `config_parameters` desde a fase 0 e nunca
    # tinham de onde sair. Agora saem da zona da rota e da preferência de risco
    # do usuário (`calculations/risk.py`).
    loss_probability: float | None = None
    """Probabilidade de perder a carga na rota, de 0 a 1."""

    distance_factor: float | None = None
    """Proximidade já normalizada, de 0 (longe/perigoso) a 1 (mesma cidade)."""


@dataclass(frozen=True)
class ScoreResult:
    score: int | None
    confidence: float
    band: str
    components: dict[str, float] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)


def _band(score: int, bands: dict[str, list[int]]) -> str:
    for nome, (minimo, maximo) in bands.items():
        if minimo <= score <= maximo:
            return nome
    return "desconhecida"


DEFAULT_BANDS = {
    "ruim": [0, 39],
    "moderada": [40, 59],
    "boa": [60, 74],
    "muito_boa": [75, 89],
    "excelente": [90, 100],
}


# Abaixo desta fração do peso previsto, o score não é publicado. Um número alto
# calculado só com frescor e liquidez, sem lucro nem margem, é pior do que não
# ter score: ele dá confiança a uma oportunidade que ninguém avaliou.
MIN_CONFIDENCE = 0.5


def compute_score(
    inputs: ScoreInputs,
    weights: dict[str, float],
    references: dict[str, float] | None = None,
    bands: dict[str, list[int]] | None = None,
    min_confidence: float = MIN_CONFIDENCE,
) -> ScoreResult:
    ref = {**DEFAULT_REFERENCES, **(references or {})}
    faixas = bands or DEFAULT_BANDS

    normalizados: dict[str, float] = {}
    faltando: list[str] = []

    if inputs.profit is not None:
        normalizados["profit"] = _clamp(inputs.profit / ref["profit_silver"])
    else:
        faltando.append("profit")

    if inputs.margin_pct is not None:
        normalizados["margin"] = _clamp(inputs.margin_pct / ref["margin_pct"])
    else:
        faltando.append("margin")

    if inputs.roi_pct is not None:
        normalizados["roi"] = _clamp(inputs.roi_pct / ref["roi_pct"])
    else:
        faltando.append("roi")

    if inputs.freshness_seconds is not None:
        # Decai linearmente: preço de agora vale 1, preço de 6 h vale 0.
        normalizados["freshness"] = _clamp(
            1 - inputs.freshness_seconds / ref["freshness_seconds"]
        )
    else:
        faltando.append("freshness")

    if inputs.liquidity_units_per_day is not None:
        normalizados["liquidity"] = _clamp(
            inputs.liquidity_units_per_day / ref["liquidity_units_per_day"]
        )
    else:
        faltando.append("liquidity")

    if inputs.loss_probability is not None:
        # Risco entra invertido: probabilidade de perda alta é score baixo.
        normalizados["risk"] = _clamp(1 - inputs.loss_probability)
    else:
        faltando.append("risk")

    if inputs.distance_factor is not None:
        normalizados["distance"] = _clamp(inputs.distance_factor)
    else:
        faltando.append("distance")

    if inputs.trend_pct is not None:
        # Tendência de alta no destino favorece; de queda penaliza. Centrado em
        # 0,5 para que "sem movimento" seja neutro, não ruim.
        normalizados["trend"] = _clamp(0.5 + inputs.trend_pct / 40.0)
    else:
        faltando.append("trend")

    peso_total = sum(weights.get(nome, 0.0) for nome in normalizados)
    if peso_total <= 0:
        return ScoreResult(None, 0.0, "desconhecida", {}, faltando)

    bruto = sum(weights.get(nome, 0.0) * valor for nome, valor in normalizados.items())
    score = int(round(bruto / peso_total * 100))

    # Confiança é a fração do peso originalmente previsto que pôde ser usada.
    peso_previsto = sum(weights.values()) or 1.0
    confianca = round(peso_total / peso_previsto, 2)

    if confianca < min_confidence:
        return ScoreResult(None, confianca, "desconhecida", {}, faltando)

    return ScoreResult(
        score=score,
        confidence=confianca,
        band=_band(score, faixas),
        components={nome: round(valor, 3) for nome, valor in normalizados.items()},
        missing=faltando,
    )
