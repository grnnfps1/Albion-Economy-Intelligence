"""Estatística robusta de série de preço.

O caso central vem de dado real: T4_BAG qualidade 2 em Lymhurst registrou
3.625 → 29.790 → 3.737 em dias consecutivos na validação do AODP.
"""

import pytest

from app.calculations.statistics import (
    Trend,
    classify_trend,
    flag_outliers,
    median_absolute_deviation,
    modified_z_scores,
    percentage_change,
    summarize,
)

# Série real, com o pico de 16/08 no meio.
LYMHURST = [3716, 3525, 3625, 29790, 3737, 3701, 3718, 3847, 3919, 3895]


class TestMad:
    def test_mad_ignora_o_extremo(self):
        """Desvio padrão seria inflado pelo próprio outlier; MAD não é."""
        assert median_absolute_deviation(LYMHURST) < 150

    def test_serie_constante_tem_mad_zero(self):
        assert median_absolute_deviation([100, 100, 100]) == 0.0

    def test_lista_vazia_nao_estoura(self):
        assert median_absolute_deviation([]) == 0.0


class TestOutliers:
    def test_pico_real_e_marcado(self):
        marks = flag_outliers([float(v) for v in LYMHURST])
        assert marks[3] is True
        assert sum(marks) == 1

    def test_serie_saudavel_nao_marca_nada(self):
        assert not any(flag_outliers([3700.0, 3750.0, 3690.0, 3800.0, 3720.0, 3760.0]))

    def test_serie_curta_nao_e_avaliada(self):
        """Com 4 pontos, qualquer critério marcaria metade da amostra."""
        assert flag_outliers([100.0, 100.0, 100.0, 9000.0]) == [False] * 4

    def test_mad_zero_nao_divide_por_zero(self):
        """Metade dos valores idênticos zera o MAD."""
        marks = flag_outliers([100.0, 100.0, 100.0, 100.0, 100.0, 9000.0])
        assert marks[-1] is True

    def test_serie_totalmente_constante(self):
        assert not any(flag_outliers([100.0] * 6))

    def test_limiar_e_ajustavel(self):
        values = [100.0, 102.0, 98.0, 101.0, 99.0, 130.0]
        frouxo = sum(flag_outliers(values, threshold=10.0))
        rigido = sum(flag_outliers(values, threshold=2.0))
        assert frouxo <= rigido

    def test_zscore_de_serie_curta_e_neutro(self):
        assert modified_z_scores([1.0, 2.0]) == [0.0, 0.0]


class TestSummarize:
    def test_resumo_ignora_o_outlier(self):
        values = [float(v) for v in LYMHURST]
        summary = summarize(values, flag_outliers(values))

        assert summary.outlier_count == 1
        assert summary.count == 9
        # Sem o filtro, o máximo seria 29.790 e a média passaria de 6.000.
        assert summary.maximum == 3919
        assert summary.average < 4000

    def test_sem_filtro_o_lixo_entra(self):
        """Demonstra o que a marcação evita."""
        sem_filtro = summarize([float(v) for v in LYMHURST])
        assert sem_filtro.maximum == 29790
        assert sem_filtro.average > 6000

    def test_serie_vazia(self):
        summary = summarize([])
        assert summary.has_data is False
        assert summary.median_value is None

    def test_todos_os_pontos_marcados(self):
        summary = summarize([1.0, 2.0], [True, True])
        assert summary.count == 0
        assert summary.average is None
        assert summary.outlier_count == 2

    def test_mediana_e_media_divergem_em_serie_assimetrica(self):
        summary = summarize([100.0, 100.0, 100.0, 100.0, 500.0])
        assert summary.median_value == 100.0
        assert summary.average == 180.0


class TestVariacao:
    def test_variacao_percentual(self):
        assert percentage_change(110.0, 100.0) == pytest.approx(10.0)
        assert percentage_change(90.0, 100.0) == pytest.approx(-10.0)

    def test_referencia_zero_nao_vira_infinito(self):
        assert percentage_change(100.0, 0.0) is None

    def test_sem_dado_devolve_none(self):
        assert percentage_change(None, 100.0) is None
        assert percentage_change(100.0, None) is None


class TestTendencia:
    def test_ruido_pequeno_e_estavel(self):
        """1% não é tendência."""
        assert classify_trend(101.0, 100.0) is Trend.FLAT

    def test_alta_e_baixa(self):
        assert classify_trend(120.0, 100.0) is Trend.UP
        assert classify_trend(80.0, 100.0) is Trend.DOWN

    def test_faixa_de_estabilidade_e_parametrizavel(self):
        assert classify_trend(110.0, 100.0, flat_band_pct=15.0) is Trend.FLAT

    def test_sem_referencia_e_desconhecida(self):
        assert classify_trend(100.0, None) is Trend.UNKNOWN
