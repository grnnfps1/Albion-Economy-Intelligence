"""Taxa de retorno: a fórmula `RRR = B / (1 + B)`.

Até a fase 19 isto era uma tabela de valores medidos. A fase 20 guarda os
bônus oficiais e deriva a taxa — e os testes abaixo são, antes de tudo, a
conferência de que a fórmula reproduz o que a comunidade mediu.
"""

import pytest

from app.calculations.returns import (
    Activity,
    ReturnComponents,
    resolve_return_rate,
    rrr_from_bonus,
    total_bonus,
)

# Os quatro bônus oficiais.
OFICIAIS = ReturnComponents(
    city_base=0.18, refining_city=0.40, crafting_city=0.15, focus=0.59
)


def taxa(activity, bonus_cidade, foco, ilha=False, override=None):
    return resolve_return_rate(OFICIAIS, activity, bonus_cidade, foco, ilha, override)


class TestAFormulaReproduzOMedido:
    """A conferência que justifica trocar a tabela pela fórmula."""

    @pytest.mark.parametrize(
        "atividade,bonus,foco,medido",
        [
            (Activity.REFINING, False, False, 0.152),
            (Activity.REFINING, True, False, 0.367),
            (Activity.REFINING, False, True, 0.435),
            (Activity.REFINING, True, True, 0.539),
            (Activity.CRAFTING, False, False, 0.152),
            (Activity.CRAFTING, True, False, 0.248),
            (Activity.CRAFTING, False, True, 0.435),
        ],
    )
    def test_cenarios_publicados(self, atividade, bonus, foco, medido):
        assert taxa(atividade, bonus, foco).rate == pytest.approx(medido, abs=0.001)

    def test_a_celula_que_a_formula_corrigiu(self):
        """Craft com bônus de cidade **e** foco.

        A fase 14 gravou 0,477; a fórmula dá 0,4792. O desvio é dez vezes o de
        qualquer outra célula (todas abaixo de 0,0006), então é o valor tabelado
        que estava impreciso — não a fórmula.
        """
        assert taxa(Activity.CRAFTING, True, True).rate == pytest.approx(0.4792, abs=0.0005)


class TestOImpasseEraAparente:
    def test_quarenta_por_cento_de_bonus_dao_36_7_de_retorno(self):
        """A doc oficial diz +40%; a comunidade mede 36,7%. Os dois estão certos.

        O bônus é o que a estação soma; o retorno é a fração que volta. `B/(1+B)`
        é a conversão entre os dois, e é por isso que o número da comunidade tem
        decimal.
        """
        assert rrr_from_bonus(0.18 + 0.40) == pytest.approx(0.367, abs=0.001)


class TestIlha:
    def test_ilha_sem_foco_nao_devolve_nada(self):
        """Sem a base de cidade, `B = 0` e o retorno é zero de verdade."""
        resultado = taxa(Activity.REFINING, False, False, ilha=True)
        assert resultado.rate == 0.0
        assert resultado.is_island is True

    def test_ilha_com_foco(self):
        assert taxa(Activity.REFINING, False, True, ilha=True).rate == pytest.approx(
            0.371, abs=0.001
        )

    def test_ilha_rende_menos_que_cidade_nos_dois_casos(self):
        for foco in (False, True):
            assert (
                taxa(Activity.REFINING, False, foco, ilha=True).rate
                < taxa(Activity.REFINING, False, foco).rate
            )


class TestComposicao:
    def test_os_bonus_somam_antes_da_conversao(self):
        """É a diferença entre somar bônus e somar taxas."""
        b = total_bonus(OFICIAIS, Activity.REFINING, True, True)
        assert b == pytest.approx(1.17)
        # Somar as taxas daria 0,152 + 0,367 + 0,435, que passa de 1.
        assert taxa(Activity.REFINING, True, True).rate < 1

    def test_refino_e_craft_usam_bonus_de_cidade_diferentes(self):
        assert total_bonus(OFICIAIS, Activity.REFINING, True, False) == pytest.approx(0.58)
        assert total_bonus(OFICIAIS, Activity.CRAFTING, True, False) == pytest.approx(0.33)

    def test_a_taxa_nunca_passa_de_um(self):
        """Propriedade da fórmula: protege contra bônus absurdo."""
        assert rrr_from_bonus(1e9) < 1
        assert rrr_from_bonus(0) == 0


class TestParametroAusente:
    def test_componente_faltando_e_unknown_e_nao_zero(self):
        incompleto = ReturnComponents(city_base=0.18, focus=0.59)
        resultado = resolve_return_rate(incompleto, Activity.REFINING, True, True)
        assert resultado.known is False
        assert resultado.source == "UNKNOWN"

    def test_o_que_falta_e_nomeado(self):
        incompleto = ReturnComponents(city_base=0.18)
        assert "refining.return_bonus.city" in incompleto.missing()


class TestSobrescrita:
    def test_preferencia_do_usuario_vence_a_formula(self):
        resultado = taxa(Activity.REFINING, True, True, override=0.62)
        assert resultado.rate == 0.62
        assert resultado.source == "preferencia"

    def test_a_taxa_da_formula_continua_visivel_para_comparar(self):
        resultado = taxa(Activity.REFINING, True, True, override=0.62)
        assert resultado.formula_rate == pytest.approx(0.539, abs=0.001)

    def test_sobrescrita_e_limitada_a_faixa(self):
        assert taxa(Activity.REFINING, False, False, override=5).rate == 1.0
        assert taxa(Activity.REFINING, False, False, override=-1).rate == 0.0


class TestAuditoria:
    def test_a_resposta_carrega_o_b_para_conferencia(self):
        """`rate` sozinho não é conferível; com `B` a conta se refaz na mão."""
        resultado = taxa(Activity.REFINING, True, False)
        assert resultado.bonus_total == pytest.approx(0.58)
        assert resultado.source == "formula"
