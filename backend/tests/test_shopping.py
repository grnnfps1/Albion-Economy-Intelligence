"""Lista de compras: o retorno reduz o consumo, e o arredondamento é para cima."""

import math

import pytest

from app.calculations.shopping import effective_units, shopping_line


class TestConsumoEfetivo:
    def test_o_exemplo_do_couro_t8(self):
        """5 pelegos por unidade, 100 unidades, 36,7% de retorno → 317."""
        assert effective_units(quantity=100, per_unit=5, return_rate=0.367) == 317

    def test_sem_retorno_o_consumo_e_a_receita_cheia(self):
        assert effective_units(quantity=100, per_unit=5, return_rate=0.0) == 500

    def test_arredonda_para_cima(self):
        """Não se compra 316,5 pelegos — e faltar material no meio é pior."""
        # 100 × 5 × 0,633 = 316,5
        assert effective_units(100, 5, 0.367) == 317

    def test_arredonda_para_cima_tambem_em_fracao_minima(self):
        assert effective_units(1, 1, 0.99) == 1

    def test_retorno_desconhecido_nao_aplica_desconto(self):
        """Supor retorno cheio deixaria a produção parada no meio."""
        assert effective_units(100, 5, None) == 500

    def test_retorno_fora_da_faixa_e_limitado(self):
        assert effective_units(100, 5, 1.5) == 0
        assert effective_units(100, 5, -1) == 500

    def test_quantidade_zero_nao_compra_nada(self):
        assert effective_units(0, 5, 0.367) == 0


class TestLinha:
    def test_a_linha_mostra_o_que_o_retorno_poupou(self):
        linha = shopping_line("T8_HIDE", quantity=100, per_unit=5, return_rate=0.367)
        assert linha.gross == 500
        assert linha.units == 317
        assert linha.saved == 183

    def test_sem_retorno_nao_poupa_nada(self):
        linha = shopping_line("T8_HIDE", quantity=10, per_unit=5, return_rate=0.0)
        assert linha.gross == 50
        assert linha.units == 50
        assert linha.saved == 0


class TestArredondaUmaVezNoFim:
    """Arredondar por unidade e multiplicar infla a compra.

    A conta certa é `⌈quantidade × receita × (1 − retorno)⌉`: o teto entra uma
    única vez, sobre o consumo total. A errada é `⌈receita × (1 − retorno)⌉ ×
    quantidade`, e ela transforma fração de sobra por unidade em pilha de
    material parado.
    """

    def test_a_sobra_por_unidade_vira_montanha_na_quantidade(self):
        """5 pelegos por unidade, 36,71% de retorno, 500 unidades.

        Certo: `⌈500 × 5 × 0,6329⌉ = 1.583`. Por unidade daria `⌈3,1645⌉ = 4`,
        e `4 × 500 = 2.000` — **417 pelegos a mais**, 26% de compra inventada.
        """
        certo = effective_units(500, 5, 0.3671)
        por_unidade = math.ceil(5 * (1 - 0.3671)) * 500
        assert certo == 1583
        assert por_unidade == 2000
        assert por_unidade - certo == 417

    @pytest.mark.parametrize("quantidade", [1, 7, 100, 500, 10_000])
    def test_nunca_compra_mais_que_a_conta_por_unidade(self, quantidade):
        """Propriedade: o teto único é sempre ≤ o teto por unidade."""
        for por_unidade_receita in (1, 2, 5, 8):
            for taxa in (0.0, 0.152, 0.3671, 0.539):
                assert effective_units(quantidade, por_unidade_receita, taxa) <= (
                    math.ceil(por_unidade_receita * (1 - taxa)) * quantidade
                )

    def test_o_excesso_e_no_maximo_uma_unidade(self):
        """O teto único compra, no máximo, um material a mais que o exato.

        É o que autoriza dizer "arredondado para cima" na tela sem ressalva de
        magnitude: a folga não cresce com a quantidade.
        """
        for quantidade in (1, 13, 500, 10_000):
            exato = quantidade * 5 * (1 - 0.3671)
            assert 0 <= effective_units(quantidade, 5, 0.3671) - exato < 1
