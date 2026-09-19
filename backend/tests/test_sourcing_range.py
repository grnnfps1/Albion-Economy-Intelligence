"""Intervalo de preço entre cidades: o que a escolha deixou na mesa.

`MaterialSourcing` decide *onde* comprar; o intervalo responde outra coisa —
*quanto a decisão importou*. Sem ele a tela mostra só o preço usado, e o
usuário não sabe se economizou muito ou se a escolha foi indiferente.
"""

import pytest

from app.services.sourcing import MaterialSourcing, Quote, SourcingMode

FRESCO = 600
VELHO = 90_000


def cotacao(slug, preco, idade=FRESCO, manual=False):
    return Quote(
        location_slug=slug, location_name=slug.title(),
        unit_price=preco, age_seconds=idade, is_manual=manual,
    )


def politica(cotacoes, modo=SourcingMode.SINGLE_CITY, base="caerleon"):
    return MaterialSourcing(modo, base, {"T4_HIDE": cotacoes}, max_age_seconds=21_600)


class TestOIntervalo:
    def test_menor_maior_e_a_diferenca_em_percentual(self):
        faixa = politica([
            cotacao("caerleon", 103), cotacao("thetford", 95), cotacao("martlock", 114),
        ]).range_of("T4_HIDE")
        assert (faixa.min_price, faixa.max_price) == (95, 114)
        assert faixa.spread == 19
        # Sobre o menor preço: quanto a mais custa a cidade cara.
        assert faixa.spread_pct == pytest.approx(20.0, abs=0.1)

    def test_as_cidades_vem_ordenadas_por_preco(self):
        faixa = politica([
            cotacao("caerleon", 103), cotacao("thetford", 95), cotacao("martlock", 114),
        ]).range_of("T4_HIDE")
        assert [c.location_slug for c in faixa.cities] == ["thetford", "caerleon", "martlock"]

    def test_a_escolhida_vem_marcada(self):
        faixa = politica([cotacao("caerleon", 103), cotacao("thetford", 95)]).range_of("T4_HIDE")
        escolhidas = [c.location_slug for c in faixa.cities if c.is_chosen]
        # Em CIDADE_UNICA a compra é na base, mesmo havendo mais barato fora.
        assert escolhidas == ["caerleon"]


class TestCotacaoVelhaNaoEntra:
    """Mesma regra que governa a escolha desde a fase 11.

    Incluir cotação velha faria o intervalo parecer maior do que a decisão
    real, e o "maior preço" seria sempre a cidade que ninguém visita.
    """

    def test_a_velha_fica_fora_do_intervalo(self):
        faixa = politica([
            cotacao("caerleon", 100), cotacao("thetford", 90),
            cotacao("lymhurst", 500, idade=VELHO),
        ]).range_of("T4_HIDE")
        assert faixa.max_price == 100
        assert faixa.fresh_city_count == 2

    def test_mas_continua_na_lista_do_balao(self):
        """Ver que Lymhurst tem preço de três dias atrás é informação."""
        faixa = politica([
            cotacao("caerleon", 100), cotacao("thetford", 90),
            cotacao("lymhurst", 500, idade=VELHO),
        ]).range_of("T4_HIDE")
        velhas = [c for c in faixa.cities if not c.is_fresh]
        assert [c.location_slug for c in velhas] == ["lymhurst"]

    def test_cotacao_sem_data_nao_e_fresca(self):
        """Idade desconhecida não autoriza entrar no intervalo, como na escolha."""
        faixa = politica([
            cotacao("caerleon", 100), cotacao("thetford", 90, idade=None),
        ]).range_of("T4_HIDE")
        assert faixa.comparable is False


class TestUmaCotacaoSoNaoEIntervalo:
    """É falta de alternativa, e muda a confiança no número.

    Um intervalo de zero diria "todas as cidades cobram igual" — afirmação
    sobre o mercado. Falta de alternativa é afirmação sobre o que se sabe dele,
    e a tela precisa dizer as duas de formas diferentes.
    """

    def test_uma_cidade_fresca_nao_e_comparavel(self):
        faixa = politica([cotacao("caerleon", 100)]).range_of("T4_HIDE")
        assert faixa.comparable is False
        assert faixa.spread is None and faixa.spread_pct is None
        assert faixa.fresh_city_count == 1

    def test_nenhuma_cotacao_devolve_lista_vazia(self):
        faixa = politica([]).range_of("T4_HIDE")
        assert faixa.cities == []
        assert faixa.comparable is False

    def test_duas_cidades_com_o_mesmo_preco_sao_comparaveis_com_zero(self):
        """Aqui zero é afirmação de verdade: duas cidades, e cobram igual."""
        faixa = politica([cotacao("caerleon", 100), cotacao("thetford", 100)]).range_of("T4_HIDE")
        assert faixa.comparable is True
        assert faixa.spread == 0
        assert faixa.spread_pct == 0.0


class TestOModoNaoMudaOIntervalo:
    """O intervalo informa; o modo decide. São coisas separadas de propósito."""

    @pytest.mark.parametrize("modo", list(SourcingMode))
    def test_o_intervalo_e_o_mesmo_em_qualquer_modo(self, modo):
        cotacoes = [cotacao("caerleon", 103), cotacao("thetford", 95)]
        faixa = politica(cotacoes, modo=modo).range_of("T4_HIDE")
        assert (faixa.min_price, faixa.max_price) == (95, 103)

    def test_mas_a_cidade_escolhida_muda(self):
        cotacoes = [cotacao("caerleon", 103), cotacao("thetford", 95)]
        unica = politica(cotacoes, modo=SourcingMode.SINGLE_CITY).choose("T4_HIDE")
        barato = politica(cotacoes, modo=SourcingMode.CHEAPEST).choose("T4_HIDE")
        assert unica.quote.location_slug == "caerleon"
        assert barato.quote.location_slug == "thetford"
