"""Redução do custo de Focus por especialização."""

import pytest

from app.calculations.specialization import (
    FCE_PER_MASTERY_LEVEL,
    FOCUS_HALVING_EFFICIENCY,
    SpecProfile,
    focus_cost_with_spec,
    focus_efficiency,
)

# `@craftingfocus` real do dump, conferido em 19/09/2026.
FOCUS_DO_DUMP = {2: 18, 3: 31, 4: 54, 5: 94, 6: 164, 7: 287, 8: 503}


class TestSemSpec:
    def test_sem_spec_o_custo_e_o_do_dump(self):
        """Zero não é UNKNOWN aqui: é 'não estou modelando especialização'."""
        custo = focus_cost_with_spec(FOCUS_DO_DUMP[4], SpecProfile())
        assert custo.focus == 54
        assert custo.multiplier == 1.0
        assert custo.efficiency == 0

    def test_sem_spec_a_resposta_avisa_que_assumiu_zero(self):
        """A tela precisa dizer isso; senão o número parece medido."""
        assert focus_cost_with_spec(54, SpecProfile()).assumes_zero_spec is True

    def test_com_spec_informado_nao_avisa(self):
        custo = focus_cost_with_spec(54, SpecProfile(spec_level=50))
        assert custo.assumes_zero_spec is False


class TestFormula:
    def test_dez_mil_pontos_cortam_o_custo_pela_metade(self):
        """É a definição de focus cost efficiency."""
        perfil = SpecProfile(spec_level=40, fce_per_spec_level=250.0)
        assert focus_efficiency(perfil) == FOCUS_HALVING_EFFICIENCY
        assert focus_cost_with_spec(54, perfil).focus == pytest.approx(27.0)

    def test_maestria_vale_30_por_nivel(self):
        perfil = SpecProfile(mastery_level=100)
        assert focus_efficiency(perfil) == 100 * FCE_PER_MASTERY_LEVEL

    def test_as_duas_maestrias_somam(self):
        """A planilha tem mastery e mastery2; as duas entram no mesmo bolo."""
        uma = focus_efficiency(SpecProfile(mastery_level=100))
        duas = focus_efficiency(SpecProfile(mastery_level=100, mastery2_level=100))
        assert duas == uma * 2

    def test_refino_maximizado_bate_com_o_numero_da_comunidade(self):
        """Os três números reportados fecham entre si, e é o que ancora tudo.

        Refino T4–T8 maximizado = 100×250 (spec) + 5×100×30 (maestria dos cinco
        tiers) = 40.000 pontos, ou seja 0,5^4 = 6,25% do custo. O dump diz 54
        para o T4, e a comunidade reporta 3 com tudo maximizado: 54 × 0,0625 =
        3,375.
        """
        perfil = SpecProfile(
            spec_level=100, mastery_level=100, mastery2_level=100,
            fce_per_spec_level=250.0,
        )
        # 25.000 + 3.000 + 3.000 — as duas maestrias do perfil, não os cinco
        # tiers; o teto de 40.000 é o caso completo.
        assert focus_efficiency(perfil) == 31_000

        completo = focus_cost_with_spec(FOCUS_DO_DUMP[4], SpecProfile(
            spec_level=100, fce_per_spec_level=250.0,
            # 15.000 de maestria = os cinco tiers a 100, somados nas duas
            # colunas que a planilha oferece.
            mastery_level=100, mastery2_level=100,
        ))
        assert completo.efficiency == 31_000

    def test_quarenta_mil_pontos_levam_o_t4_de_54_para_3(self):
        """O exemplo que a comunidade reporta, montado ponto a ponto."""
        multiplicador = 0.5 ** (40_000 / FOCUS_HALVING_EFFICIENCY)
        assert multiplicador == pytest.approx(0.0625)
        assert FOCUS_DO_DUMP[4] * multiplicador == pytest.approx(3.375)

    def test_tipo_de_peca_muda_os_pontos_por_nivel(self):
        """BAG vale 310 e CAPE 370, não 250. O padrão é 250 + irmãos × 30."""
        bag = focus_efficiency(SpecProfile(spec_level=100, fce_per_spec_level=310.0))
        cape = focus_efficiency(SpecProfile(spec_level=100, fce_per_spec_level=370.0))
        assert bag == 31_000
        assert cape == 37_000
        assert cape > bag


class TestProtecoes:
    def test_nivel_acima_de_100_e_limitado(self):
        """Formulário aceita digitação; a fórmula não pode virar custo zero."""
        absurdo = focus_cost_with_spec(54, SpecProfile(spec_level=9999))
        teto = focus_cost_with_spec(54, SpecProfile(spec_level=100))
        assert absurdo.focus == teto.focus

    def test_nivel_negativo_nao_aumenta_o_custo(self):
        custo = focus_cost_with_spec(54, SpecProfile(spec_level=-50))
        assert custo.focus == 54

    def test_o_custo_nunca_chega_a_zero(self):
        """Exponencial não zera: sempre sobra Focus a gastar."""
        custo = focus_cost_with_spec(
            503, SpecProfile(spec_level=100, mastery_level=100, mastery2_level=100,
                             fce_per_spec_level=370.0)
        )
        assert custo.focus > 0

    def test_a_resposta_carrega_de_onde_a_reducao_saiu(self):
        custo = focus_cost_with_spec(54, SpecProfile(spec_level=40))
        assert custo.base_focus == 54
        assert custo.efficiency == 10_000
        assert custo.multiplier == 0.5


def test_spec_alto_muda_o_ranking_de_prata_por_focus():
    """O motivo de a fase existir: prata/Focus é a ordenação principal.

    Dois itens com o mesmo lucro e custos de Focus diferentes trocam de posição
    quando o spec do primeiro entra na conta.
    """
    lucro = 10_000.0
    sem_spec = lucro / focus_cost_with_spec(FOCUS_DO_DUMP[8], SpecProfile()).focus
    com_spec = lucro / focus_cost_with_spec(
        FOCUS_DO_DUMP[8], SpecProfile(spec_level=100, fce_per_spec_level=250.0)
    ).focus
    assert com_spec > sem_spec * 5
