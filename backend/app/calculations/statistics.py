"""Estatística de série de preço.

Funções puras: entra lista de números, sai número. Sem banco, sem rede, sem
relógio. É o que permite testar o comportamento em outliers reais sem subir nada.

Por que mediana e não média: o endpoint de histórico do AODP **já devolve média**
por bucket, e uma única ordem manipulada contamina o bucket inteiro. Visto na
validação de T4_BAG q2 em Lymhurst: 3.625 → 29.790 → 3.737 em dias consecutivos.
Tirar média de médias contaminadas propaga o lixo para a "média de 7 dias" que o
usuário vê e para a margem que o motor de oportunidades calcula.
"""

from dataclasses import dataclass
from enum import StrEnum
from statistics import median


class Trend(StrEnum):
    UP = "ALTA"
    FLAT = "ESTAVEL"
    DOWN = "BAIXA"
    UNKNOWN = "DESCONHECIDA"


def median_absolute_deviation(values: list[float]) -> float:
    """MAD: mediana das distâncias até a mediana.

    Desvio padrão não serve aqui: ele é calculado a partir da média e, num
    conjunto com um valor oito vezes maior que os outros, o próprio outlier
    infla o desvio a ponto de deixar de ser detectado.
    """
    if not values:
        return 0.0
    center = median(values)
    return float(median([abs(value - center) for value in values]))


def modified_z_scores(values: list[float]) -> list[float]:
    """Z-score robusto, baseado em mediana e MAD.

    A constante 0.6745 é o que torna o MAD comparável ao desvio padrão numa
    distribuição normal -- sem ela o limiar não teria significado estável.

    Quando o MAD é zero (metade ou mais dos valores idênticos), cai para o desvio
    absoluto médio. Sem esse cuidado, uma série estável com um pico dividiria por
    zero.
    """
    if len(values) < 3:
        return [0.0] * len(values)

    center = median(values)
    mad = median_absolute_deviation(values)

    if mad == 0:
        mean_deviation = sum(abs(value - center) for value in values) / len(values)
        if mean_deviation == 0:
            return [0.0] * len(values)
        return [abs(value - center) / (1.253314 * mean_deviation) for value in values]

    return [0.6745 * abs(value - center) / mad for value in values]


def flag_outliers(values: list[float], threshold: float = 3.5) -> list[bool]:
    """Marca os pontos suspeitos. Não remove nada.

    Apagar seria pior: um pico pode ser evento real (patch, guerra, escassez). O
    ponto fica gravado e marcado, a UI mostra, e as médias de referência o ignoram.

    Séries curtas não são avaliadas: com menos de 5 pontos, qualquer critério
    marca metade da amostra.
    """
    if len(values) < 5:
        return [False] * len(values)
    return [score > threshold for score in modified_z_scores(values)]


@dataclass(frozen=True)
class SeriesSummary:
    count: int
    minimum: float | None
    maximum: float | None
    average: float | None
    median_value: float | None
    outlier_count: int

    @property
    def has_data(self) -> bool:
        return self.count > 0


def summarize(values: list[float], outliers: list[bool] | None = None) -> SeriesSummary:
    """Resume a série ignorando os pontos marcados.

    `average` e `median_value` são calculados só sobre os pontos limpos. Já
    `minimum` e `maximum` também — mostrar o máximo de um outlier como "máximo do
    período" transformaria o lixo em informação.
    """
    marks = outliers if outliers is not None else [False] * len(values)
    clean = [value for value, is_outlier in zip(values, marks, strict=True) if not is_outlier]
    outlier_count = sum(marks)

    if not clean:
        return SeriesSummary(0, None, None, None, None, outlier_count)

    return SeriesSummary(
        count=len(clean),
        minimum=min(clean),
        maximum=max(clean),
        average=sum(clean) / len(clean),
        median_value=float(median(clean)),
        outlier_count=outlier_count,
    )


def percentage_change(current: float | None, reference: float | None) -> float | None:
    """Variação percentual. None quando não dá para calcular.

    Referência zero devolve None em vez de infinito: "subiu infinito por cento"
    não é informação.
    """
    if current is None or reference is None or reference == 0:
        return None
    return (current - reference) / reference * 100.0


def classify_trend(
    current: float | None, reference: float | None, flat_band_pct: float = 3.0
) -> Trend:
    """Alta, estável ou baixa em relação a uma referência.

    A faixa de estabilidade existe porque ruído de 1% não é tendência. O valor
    é parâmetro para poder ser calibrado com dado real.
    """
    change = percentage_change(current, reference)
    if change is None:
        return Trend.UNKNOWN
    if abs(change) <= flat_band_pct:
        return Trend.FLAT
    return Trend.UP if change > 0 else Trend.DOWN
