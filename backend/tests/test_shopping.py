"""Lista de compras: o retorno reduz o consumo, e o arredondamento é para cima."""

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
