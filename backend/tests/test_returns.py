"""Taxa de retorno: a fórmula `RRR = B / (1 + B)`.

Até a fase 19 isto era uma tabela de valores medidos. A fase 20 guarda os
bônus oficiais e deriva a taxa — e os testes abaixo são, antes de tudo, a
conferência de que a fórmula reproduz o que a comunidade mediu.
"""

import pytest

from app.calculations.returns import (
    Activity,
    ReturnComponents,
    bonus_parts,
    resolve_return_rate,
    rrr_from_bonus,
    total_bonus,
)

# Os quatro bônus oficiais.
OFICIAIS = ReturnComponents(
    city_base=0.18, refining_city=0.40, crafting_city=0.15, focus=0.59
)


def taxa(activity, bonus_cidade, foco, ilha=False, diario=0.0, override=None):
    return resolve_return_rate(
        OFICIAIS, activity, bonus_cidade, foco, ilha,
        daily_bonus=diario, override=override,
    )


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


class TestBonusDiario:
    """Quinto componente de `B`, e entrada do usuário.

    Entra **antes** da conversão, junto dos outros. Somá-lo ao `RRR` já
    convertido é a confusão que fazia as tabelas publicadas não fecharem.
    """

    def test_entra_em_B_e_nao_no_rrr(self):
        com = taxa(Activity.REFINING, True, False, diario=0.10)
        assert com.bonus_total == pytest.approx(0.68)
        assert com.rate == pytest.approx(0.68 / 1.68, abs=1e-6)

    def test_somar_ao_rrr_daria_outro_numero(self):
        """A demonstração do erro, travada em teste."""
        sem = taxa(Activity.REFINING, True, False)
        com = taxa(Activity.REFINING, True, False, diario=0.10)
        errado = sem.rate + 0.10
        assert com.rate == pytest.approx(0.4048, abs=0.001)
        assert errado == pytest.approx(0.4671, abs=0.001)
        assert com.rate < errado

    def test_padrao_zero_avisa_que_nao_foi_informado(self):
        resultado = taxa(Activity.REFINING, True, False)
        assert resultado.assumes_no_daily_bonus is True
        assert resultado.daily_bonus == 0.0

    def test_informado_deixa_de_avisar(self):
        resultado = taxa(Activity.REFINING, True, False, diario=0.05)
        assert resultado.assumes_no_daily_bonus is False

    def test_zero_nao_muda_a_taxa(self):
        """Zero significa "não estou modelando", não "o bônus é zero de fato"."""
        assert taxa(Activity.REFINING, True, False, diario=0.0).rate == pytest.approx(
            taxa(Activity.REFINING, True, False).rate
        )

    def test_negativo_e_ignorado(self):
        assert taxa(Activity.REFINING, True, False, diario=-0.5).bonus_total == pytest.approx(0.58)


class TestConferenciaContraAPlanilha:
    """Os 15 valores da aba `Validação` da planilha de referência.

    A lista **não** é replicada em lugar nenhum do código: manter uma tabela ao
    lado da fórmula garante que as duas divirjam no primeiro ajuste, e foi por
    isso que a matriz de oito células saiu de `config_parameters` na fase 20.
    Ela existe aqui como *conferência independente* — onze valores que não
    participaram da derivação e caem nas combinações previstas.
    """

    # (valor da planilha, bônus de cidade, foco, bônus diário)
    FECHAM = [
        (0.152, False, False, 0.0),
        (0.248, True, False, 0.0),
        (0.300, True, False, 0.10),
        (0.346, True, False, 0.20),
        (0.435, False, True, 0.0),
        (0.479, True, True, 0.0),
        (0.504, True, True, 0.10),
    ]

    @pytest.mark.parametrize("planilha,bonus,foco,diario", FECHAM)
    def test_craft(self, planilha, bonus, foco, diario):
        assert taxa(Activity.CRAFTING, bonus, foco, diario=diario).rate == pytest.approx(
            planilha, abs=0.001
        )

    @pytest.mark.parametrize(
        "planilha,bonus,foco,diario",
        [
            (0.367, True, False, 0.0),
            (0.404, True, False, 0.10),
            (0.539, True, True, 0.0),
            (0.559, True, True, 0.10),
        ],
    )
    def test_refino(self, planilha, bonus, foco, diario):
        assert taxa(Activity.REFINING, bonus, foco, diario=diario).rate == pytest.approx(
            planilha, abs=0.001
        )

    @pytest.mark.parametrize("planilha", [0.210, 0.310, 0.415, 0.447])
    def test_os_quatro_que_nao_fecham_continuam_sem_explicacao(self, planilha):
        """Trava o que **não** foi explicado, para ninguém "arrumar" depois.

        A distância é o que autoriza chamá-los de não explicados em vez de
        arredondamento: os onze que fecham erram no máximo 0,0008, e estes
        erram de 0,0057 a 0,0093 — sete a doze vezes mais. Se um dia aparecer
        uma combinação que os produza, é este teste que cai, e cair aqui é a
        notícia boa.
        """
        candidatas = [
            taxa(atividade, bonus, foco, ilha=ilha, diario=diario).rate
            for atividade in Activity
            for bonus in (False, True)
            for foco in (False, True)
            for ilha in (False, True)
            for diario in (0.0, 0.10, 0.20)
            if not (ilha and bonus)
        ]
        assert min(abs(c - planilha) for c in candidatas) > 0.005


class TestParcelasDeB:
    """`bonus_total` responde *quanto*; as parcelas respondem *de onde*.

    Numa tela em que o usuário escolhe cidade e Focus, `1,17` sozinho é correto
    e inacionável. `0,18 + 0,40 + 0,59` diz o que fazer.
    """

    def partes(self, **kw):
        base = dict(
            components=OFICIAIS, activity=Activity.REFINING,
            has_city_bonus=False, use_focus=False,
        )
        return bonus_parts(**(base | kw))

    def test_as_parcelas_somam_o_B(self):
        partes = self.partes(has_city_bonus=True, use_focus=True)
        assert sum(p.value for p in partes if p.applies) == pytest.approx(1.17)

    def test_a_parcela_que_nao_se_aplica_continua_na_lista(self):
        """É o que o usuário poderia ter e não tem — some da soma, não da tela."""
        partes = self.partes()
        assert [p.key for p in partes] == ["city_base", "activity_city", "focus"]
        assert [p.applies for p in partes] == [True, False, False]
        # O valor continua visível: é "40% em Martlock que você está deixando".
        assert next(p for p in partes if p.key == "activity_city").value == 0.40

    def test_a_parcela_da_cidade_muda_de_nome_com_a_atividade(self):
        refino = self.partes()
        craft = self.partes(activity=Activity.CRAFTING)
        assert refino[1].label.startswith("refino")
        assert craft[1].label.startswith("craft")
        # E de valor: 40% no refino, 15% no craft.
        assert (refino[1].value, craft[1].value) == (0.40, 0.15)

    def test_o_rotulo_carrega_a_cidade_do_bonus(self):
        """"refino em Martlock 40% (não)" diz o que fazer; sem o nome, não diz."""
        partes = self.partes(city_label="Martlock")
        assert partes[1].label == "refino em Martlock"

    def test_na_ilha_a_base_de_cidade_nao_se_aplica(self):
        """É o que faz a ilha render zero sem Focus, e o painel precisa mostrá-lo."""
        partes = self.partes(is_island=True)
        assert next(p for p in partes if p.key == "city_base").applies is False
        assert sum(p.value for p in partes if p.applies) == 0.0

    def test_o_bonus_do_dia_so_aparece_quando_informado(self):
        """Zero significa "não estou modelando" — e parcela zero na soma é ruído."""
        assert all(p.key != "daily" for p in self.partes())
        com = self.partes(daily_bonus=0.10)
        assert com[-1].key == "daily" and com[-1].value == 0.10
