"""Especialização por item: a unidade certa para craft de equipamento.

A fase 16 tratava tudo por família de recurso. Para refino isso está certo —
quem especializa couro especializa a linha. Para equipamento está errado: quem
especializou Capuz de Mercenário não especializou Capuz de Caçador.
"""

import pytest

from app.services.specialization_service import (
    SpecializationPolicy,
    parse_item_levels,
    piece_type_of,
    spec_key_of,
    tier_key_of,
)


class TestChaveDoItem:
    def test_encantamento_nunca_e_no_proprio(self):
        """`T4_PLANKS` e `T4_PLANKS_LEVEL2@2` são a mesma decisão de spec."""
        assert tier_key_of("T4_PLANKS_LEVEL2@2") == "T4_PLANKS"
        assert tier_key_of("T4_MAIN_SWORD@3") == "T4_MAIN_SWORD"

    def test_a_chave_com_tier_preserva_o_tier(self):
        """Refino especializa por tier: a aba `Spec` dá 23 ao T4 e 20 ao T5."""
        assert tier_key_of("T5_PLANKS") == "T5_PLANKS"

    def test_a_chave_de_linha_tira_o_tier(self):
        assert spec_key_of("T4_MAIN_SWORD") == "MAIN_SWORD"
        assert spec_key_of("T8_MAIN_SWORD") == "MAIN_SWORD"


class TestTipoDePeca:
    @pytest.mark.parametrize(
        "item,tipo",
        [
            ("T4_MAIN_SWORD", "MAIN"),
            ("T6_2H_AXE", "2H"),
            ("T5_ARMOR_PLATE_SET1", "ARMOR"),
            ("T5_HEAD_LEATHER_SET2", "HEAD"),
            ("T5_SHOES_CLOTH_SET3", "SHOES"),
            ("T4_OFF_SHIELD", "OFF_PRIMARY"),
            ("T4_BAG", "BAG"),
            ("T5_CAPEITEM_FW_LYMHURST", "CAPE"),
            ("T4_MEAL_SOUP", "FOOD"),
            ("T4_POTION_HEAL", "POOT"),
        ],
    )
    def test_prefixos_conferidos_contra_o_catalogo(self, item, tipo):
        assert piece_type_of(item) == tipo

    def test_ferramenta_de_coleta_nao_vira_arma_de_duas_maos(self):
        """`2H_TOOL` precisa ser testado antes de `2H`, e a ordem garante isso."""
        assert piece_type_of("T5_2H_TOOL_PICK") == "GATHERER"

    def test_tipo_desconhecido_e_none_e_nao_um_chute(self):
        """Não reconhecer usa o valor geral; adivinhar mudaria o Focus."""
        assert piece_type_of("T4_ALGUMA_COISA_NOVA") is None


class TestPrecedencia:
    FCE = {"REFINING": 250.0, "MAIN": 250.0, "BAG": 310.0}

    def politica(self, **kw):
        return SpecializationPolicy(fce_per_spec_level=self.FCE, **kw)

    def test_nivel_do_item_vence_o_da_familia(self):
        p = self.politica(levels={"LEATHER": 10}, item_levels={"LEATHER": 90})
        assert p.profile_of("T4_LEATHER").spec_level == 90

    def test_chave_com_tier_vale_so_para_aquele_tier(self):
        """É a granularidade do refino, e o motivo de o tier não ser descartado.

        Informar `T5_PLANKS` não pode especializar o T4 de carona — no Destiny
        Board são nós diferentes, com níveis diferentes.
        """
        p = self.politica(levels={"PLANKS": 40}, item_levels={"T5_PLANKS": 100})
        assert p.profile_of("T5_PLANKS").spec_level == 100
        assert p.profile_of("T4_PLANKS").spec_level == 40

    def test_chave_de_linha_vale_para_todos_os_tiers(self):
        """O atalho para quem subiu a linha por igual."""
        p = self.politica(item_levels={"PLANKS": 70})
        assert p.profile_of("T4_PLANKS").spec_level == 70
        assert p.profile_of("T8_PLANKS").spec_level == 70

    def test_a_chave_com_tier_vence_a_de_linha(self):
        p = self.politica(item_levels={"PLANKS": 70, "T8_PLANKS": 100})
        assert p.profile_of("T8_PLANKS").spec_level == 100
        assert p.profile_of("T4_PLANKS").spec_level == 70

    def test_familia_continua_valendo_para_refino(self):
        p = self.politica(levels={"PLANKS": 60})
        assert p.profile_of("T5_PLANKS").spec_level == 60

    def test_item_nao_informado_fica_em_zero(self):
        """E não herda o spec de outro item da mesma árvore."""
        p = self.politica(item_levels={"HEAD_LEATHER_SET1": 100})
        assert p.profile_of("T5_HEAD_LEATHER_SET2").spec_level == 0

    def test_capuz_de_mercenario_nao_especializa_capuz_de_cacador(self):
        """O caso que motivou a fase: dois nós diferentes do Destiny Board."""
        p = self.politica(item_levels={"HEAD_LEATHER_SET1": 100})
        mercenario = p.focus_cost_of("T6_HEAD_LEATHER_SET1", 164)
        cacador = p.focus_cost_of("T6_HEAD_LEATHER_SET2", 164)
        assert mercenario.focus < cacador.focus
        assert cacador.focus == 164

    def test_o_tipo_de_peca_escolhe_os_pontos_por_nivel(self):
        """BAG vale 310 por nível e MAIN vale 250 — mesma spec, Focus diferente."""
        p = self.politica(item_levels={"BAG": 100, "MAIN_SWORD": 100})
        assert p.profile_of("T4_BAG").fce_per_spec_level == 310.0
        assert p.profile_of("T4_MAIN_SWORD").fce_per_spec_level == 250.0


class TestAvisoDeZero:
    def test_spec_so_por_item_ja_conta_como_informado(self):
        p = SpecializationPolicy(item_levels={"MAIN_SWORD": 40})
        assert p.informed is True

    def test_tudo_zero_continua_avisando(self):
        p = SpecializationPolicy(levels={"LEATHER": 0}, item_levels={"MAIN_SWORD": 0})
        assert p.informed is False


class TestParse:
    def test_a_granularidade_digitada_e_preservada(self):
        assert parse_item_levels("T5_PLANKS:100,MAIN_SWORD:80") == {
            "T5_PLANKS": 100,
            "MAIN_SWORD": 80,
        }

    def test_o_encantamento_sai_sempre(self):
        assert parse_item_levels("T5_PLANKS_LEVEL2@2:60") == {"T5_PLANKS": 60}

    def test_entrada_torta_e_ignorada_e_nao_derruba_a_rota(self):
        """Um parâmetro de URL malformado não pode tirar a tela do ar."""
        assert parse_item_levels("MAIN_SWORD:oi,,:,BAG:50") == {"BAG": 50}

    def test_nivel_e_limitado_a_0_100(self):
        assert parse_item_levels("BAG:9999,MAIN_SWORD:-5") == {
            "BAG": 100,
            "MAIN_SWORD": 0,
        }

    def test_vazio_vira_dicionario_vazio(self):
        assert parse_item_levels(None) == {}
        assert parse_item_levels("") == {}
