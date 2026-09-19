"""Ordenação da tabela do calculador.

Comparar lucro é aritmética de negócio e por isso mora no backend (regra 3).
O que a tela faz é reescrever a URL e desenhar a seta.
"""

import pytest

from app.schemas.calculator import CalcRowOut
from app.services.calculator_service import DEFAULT_SORT, SORTABLE, _ordena


def linha(rotulo, tier, encanto, *, lucro=None, investe=None, custo=None, conhecida=True):
    return CalcRowOut(
        item=f"T{tier}_LEATHER", tier=tier, enchantment=encanto, tier_label=rotulo,
        profit=lucro, total_investment=investe, production_cost=custo, known=conhecida,
    )


TABELA = [
    linha("T6.0", 6, 0, lucro=300, investe=3_000, custo=2_000),
    linha("T5.4", 5, 4, lucro=100, investe=9_000, custo=8_000),
    linha("T8.4", 8, 4, conhecida=False),
    linha("T6.2", 6, 2, lucro=-50, investe=5_000, custo=5_500),
    linha("T2.0", 2, 0, lucro=900, investe=100, custo=80),
]


def rotulos(linhas):
    return [linha.tier_label for linha in linhas]


class TestPorTier:
    def test_o_par_tier_encantamento_ordena_e_nao_o_rotulo(self):
        """T5.4 vem **antes** de T6.0.

        Por texto, `"T5.4" < "T6.0"` funciona por coincidência — e quebraria no
        dia em que existir um T10, que como string viria antes de T2.
        """
        assert rotulos(_ordena(TABELA, "tier", desc=False)) == [
            "T2.0", "T5.4", "T6.0", "T6.2", "T8.4"
        ]

    def test_decrescente_inverte_a_sequencia_inteira(self):
        """Quem só produz T7 e T8 não quer rolar catorze linhas toda vez."""
        assert rotulos(_ordena(TABELA, "tier", desc=True)) == [
            "T8.4", "T6.2", "T6.0", "T5.4", "T2.0"
        ]

    def test_a_linha_sem_calculo_NAO_vai_para_o_fim(self):
        """Aqui a posição é intrínseca ao item, não ao resultado.

        T8.4 está sem cotação e mesmo assim abre a lista decrescente: jogá-la
        para o fim quebraria a sequência que esta ordenação existe para mostrar.
        """
        assert rotulos(_ordena(TABELA, "tier", desc=True))[0] == "T8.4"
        assert rotulos(_ordena(TABELA, "tier", desc=False))[-1] == "T8.4"


class TestPorValor:
    @pytest.mark.parametrize(
        "coluna,esperado",
        [
            ("profit", ["T2.0", "T6.0", "T5.4", "T6.2"]),
            ("total_investment", ["T5.4", "T6.2", "T6.0", "T2.0"]),
            ("production_cost", ["T5.4", "T6.2", "T6.0", "T2.0"]),
        ],
    )
    def test_decrescente(self, coluna, esperado):
        assert rotulos(_ordena(TABELA, coluna, desc=True))[:4] == esperado

    def test_crescente_inverte_so_as_conhecidas(self):
        assert rotulos(_ordena(TABELA, "profit", desc=False))[:4] == [
            "T6.2", "T5.4", "T6.0", "T2.0"
        ]

    @pytest.mark.parametrize("coluna", ["profit", "total_investment", "production_cost"])
    @pytest.mark.parametrize("desc", [True, False])
    def test_a_bloqueada_fica_no_fim_nas_DUAS_direcoes(self, coluna, desc):
        """Lucro desconhecido não é lucro zero, e não compete com número.

        Se participasse, num `desc` com `None` valendo zero ela apareceria
        **acima** de toda linha que dá prejuízo — anunciada como melhor que um
        resultado real.
        """
        assert rotulos(_ordena(TABELA, coluna, desc))[-1] == "T8.4"

    def test_duas_bloqueadas_nao_se_atropelam(self):
        tabela = [*TABELA, linha("T7.4", 7, 4, conhecida=False)]
        fim = rotulos(_ordena(tabela, "profit", desc=True))[-2:]
        assert set(fim) == {"T8.4", "T7.4"}


class TestContrato:
    def test_o_padrao_esta_entre_as_ordenaveis(self):
        assert DEFAULT_SORT in SORTABLE

    def test_toda_coluna_ordenavel_existe_no_schema(self):
        """Trava o erro de digitar um nome de campo que não existe.

        `getattr(linha, sort_by, None)` devolveria `None` em silêncio e a
        ordenação viraria "tudo desconhecido, mantém a ordem" — sem erro nenhum.
        """
        campos = set(CalcRowOut.model_fields)
        for coluna in SORTABLE:
            assert coluna in campos, coluna

    def test_ordenar_nao_perde_nem_duplica_linha(self):
        for coluna in SORTABLE:
            for desc in (True, False):
                assert sorted(rotulos(_ordena(TABELA, coluna, desc))) == sorted(rotulos(TABELA))
