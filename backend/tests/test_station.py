"""Taxa de estação derivada do valor do item.

Os nomes descrevem a armadilha, não a implementação: o que estes testes
protegem é a diferença entre uma taxa que escala com o tier e o valor fixo de
100 que existia até a fase 14.
"""

import pytest

from app.calculations.station import (
    NUTRITION_PER_ITEM_VALUE,
    nutrition_for,
    station_fee_for,
)

# `@itemvalue` real do dump, conferido em 19/09/2026. Dobra a cada tier.
COURO = {2: 4.0, 3: 8.0, 4: 16.0, 5: 32.0, 6: 64.0, 7: 128.0, 8: 256.0}


class TestNutricao:
    def test_nutricao_e_o_item_value_vezes_a_constante_da_sandbox(self):
        assert nutrition_for(256.0) == pytest.approx(256.0 * 0.1125)
        assert NUTRITION_PER_ITEM_VALUE == 0.1125

    def test_item_sem_itemvalue_vira_none_e_nao_zero(self):
        """97 dos 455 itens rastreados não têm `@itemvalue` no dump.

        Zero ali produziria taxa zero e lucro inflado — é a regra 1 aplicada a
        um campo que parece inofensivo.
        """
        assert nutrition_for(None) is None

    def test_item_value_zero_e_um_valor_de_verdade(self):
        """`T1_HIDE` tem `@itemvalue` 0 no dump. Zero informado não é ausência."""
        assert nutrition_for(0.0) == 0.0


class TestTaxa:
    def test_exemplo_da_comunidade_fecha(self):
        """4.1 Scholar Sandals, item value 256, estação a 1000: 288 de prata.

        É o exemplo que circula nos fóruns desde o Lands Awakened, e serve de
        âncora: se a constante ou a divisão por 100 mudarem, este teste cai.
        """
        taxa = station_fee_for(item_value=256.0, fee_per_100_nutrition=1000.0)
        assert taxa.silver == pytest.approx(288.0)

    def test_a_taxa_dobra_quando_o_tier_sobe(self):
        """O motivo da fase 15 existir: 100 fixo errava nas duas pontas."""
        t4 = station_fee_for(COURO[4], 1000.0).silver
        t5 = station_fee_for(COURO[5], 1000.0).silver
        assert t5 == pytest.approx(t4 * 2)

    def test_do_t2_ao_t8_a_taxa_cresce_64_vezes(self):
        t2 = station_fee_for(COURO[2], 1000.0).silver
        t8 = station_fee_for(COURO[8], 1000.0).silver
        assert t8 == pytest.approx(t2 * 64)

    def test_encantamento_tambem_dobra(self):
        """`T8_LEATHER` = 256, `T8_LEATHER_LEVEL1` = 512. O eixo é o mesmo."""
        base = station_fee_for(256.0, 1000.0).silver
        encantado = station_fee_for(512.0, 1000.0).silver
        assert encantado == pytest.approx(base * 2)

    def test_sem_taxa_informada_e_unknown_e_nao_zero(self):
        taxa = station_fee_for(COURO[8], None)
        assert taxa.known is False
        assert taxa.silver is None
        assert "station_fee_per_100_nutrition" in taxa.reason

    def test_sem_item_value_e_unknown_e_nao_zero(self):
        taxa = station_fee_for(None, 1000.0)
        assert taxa.known is False
        assert "itemvalue" in taxa.reason

    def test_taxa_zero_informada_e_gratis_de_verdade(self):
        """Estação própria cobra zero. Isso é um valor, não uma ausência."""
        taxa = station_fee_for(COURO[8], 0.0)
        assert taxa.known is True
        assert taxa.silver == 0.0

    def test_execucoes_multiplicam(self):
        uma = station_fee_for(COURO[6], 1000.0, crafts=1).silver
        dez = station_fee_for(COURO[6], 1000.0, crafts=10).silver
        assert dez == pytest.approx(uma * 10)

    def test_a_resposta_carrega_de_onde_a_taxa_saiu(self):
        """`taxa: 2.496` sem nutrição nem item value é um número inconferível."""
        taxa = station_fee_for(COURO[8], 1000.0)
        assert taxa.item_value == 256.0
        assert taxa.nutrition == pytest.approx(28.8)
        assert taxa.fee_per_100_nutrition == 1000.0


class TestReconstrucaoDaPlanilha:
    """O que **não** fechou, travado para não ser esquecido nem forçado.

    Os três resíduos da planilha do Albion VIP não são reproduzíveis por uma
    taxa única. Cada um implica uma prata/100 nutrição diferente. Isso não
    invalida a fórmula — a Sandbox anunciou e cada estação cobra o que quer —,
    mas invalida a ideia de que os resíduos a confirmam.
    """

    RESIDUOS = {2: 5.17, 4: 29.98, 8: 2496.79}

    def test_cada_residuo_implica_uma_taxa_de_estacao_diferente(self):
        implicadas = {
            tier: residuo / (COURO[tier] * NUTRITION_PER_ITEM_VALUE / 100)
            for tier, residuo in self.RESIDUOS.items()
        }
        assert implicadas[2] == pytest.approx(1148.9, abs=1.0)
        assert implicadas[4] == pytest.approx(1665.6, abs=1.0)
        assert implicadas[8] == pytest.approx(8669.4, abs=1.0)
        # A conclusão: não há um único número que gere os três.
        assert implicadas[2] != pytest.approx(implicadas[8], rel=0.01)

    def test_a_cadeia_acumulada_nao_alcanca_o_t8_nem_com_retorno_zero(self):
        """A outra hipótese testada e descartada, por aritmética.

        Se o resíduo do T8 acumulasse a taxa de todos os elos abaixo dele, o
        teto — retorno zero, nada volta — seria a soma dos item values vezes a
        taxa que o T2 implica. Dá 656,59, contra 2.496,79 observados.
        """
        k = self.RESIDUOS[2] / COURO[2]
        teto = k * sum(COURO[tier] for tier in range(2, 9))
        assert teto == pytest.approx(656.59, abs=0.01)
        assert teto < self.RESIDUOS[8]
