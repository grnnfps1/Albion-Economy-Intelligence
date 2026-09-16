"""O que a normalização por dia conserta.

O erro que estes testes existem para impedir: comparar "lucro por ciclo" de uma
fazenda de 22 horas com "lucro por ciclo" de uma criação de 28 dias. Ordenado
assim, o ranking premia o que é lento.
"""

import pytest

from app.calculations.farming import (
    DAY_SECONDS,
    FarmInput,
    FarmOutput,
    PlanKind,
    compute_farm_cycle,
    per_day,
)
from app.calculations.fees import FeeProfile

TAXAS = FeeProfile(setup_fee_pct=0.025, sales_tax_pct=0.04, premium=True)
SEM_TAXAS = FeeProfile()

CICLO_FAZENDA = 79_200  # 22 h
CICLO_CRIACAO = 2_404_800  # 27,8 dias


def semente(preco=1000):
    return FarmInput("T1_FARM_CARROT_SEED", "Semente", 1.0, preco)


def colheita(preco=500, minimo=3, maximo=6, chance=1.0):
    return FarmOutput("T1_CARROT", "Cenoura", minimo, maximo, chance, preco)


def test_lucro_por_ciclo_vira_lucro_por_dia():
    """22 horas é menos que um dia: o lucro diário é maior que o do ciclo."""
    economia = compute_farm_cycle(
        PlanKind.CROP, [semente()], [colheita()], TAXAS, CICLO_FAZENDA, focus_cost=1000
    )

    assert economia.known is True
    assert economia.cycle_days == pytest.approx(0.9167, abs=0.001)
    # Contra os segundos, não contra `cycle_days`: esse é arredondado para
    # exibição e usá-lo aqui mediria o arredondamento, não a conversão.
    assert economia.profit_per_day == pytest.approx(
        economia.profit_per_cycle / (CICLO_FAZENDA / DAY_SECONDS), abs=0.01
    )
    assert economia.profit_per_day > economia.profit_per_cycle


def test_ciclo_longo_rende_menos_por_dia_mesmo_com_lucro_maior():
    """É a razão de a ordenação padrão ser por dia, e não por ciclo.

    Uma criação que rende dez vezes mais por ciclo, levando trinta vezes mais
    tempo, é o pior dos dois negócios — e ordenar por ciclo a colocaria em
    primeiro.
    """
    curto = compute_farm_cycle(
        PlanKind.CROP, [semente(1000)], [colheita(500)], TAXAS, CICLO_FAZENDA
    )
    longo = compute_farm_cycle(
        PlanKind.BREEDING,
        [FarmInput("T8_FARM_DRAKE_BABY", "Filhote", 1.0, 10_000)],
        [FarmOutput("T8_FARM_DRAKE_GROWN", "Adulto", 1, 1, 1.0, 40_000)],
        TAXAS,
        CICLO_CRIACAO,
    )

    assert longo.profit_per_cycle > curto.profit_per_cycle
    assert longo.profit_per_day < curto.profit_per_day


def test_prata_por_focus_e_intensiva():
    """Não muda com o tamanho do ciclo, só com o Focus gasto."""
    economia = compute_farm_cycle(
        PlanKind.CROP, [semente()], [colheita()], TAXAS, CICLO_FAZENDA, focus_cost=1000
    )
    assert economia.profit_per_focus == pytest.approx(economia.profit_per_cycle / 1000, abs=0.01)
    assert economia.focus_per_day == pytest.approx(
        1000 / (CICLO_FAZENDA / DAY_SECONDS), abs=0.01
    )


def test_sem_focus_declarado_a_prata_por_focus_e_none_e_nao_zero():
    """Adulto que dá leite não gasta Focus. Zero ali viraria divisão por zero."""
    economia = compute_farm_cycle(
        PlanKind.PRODUCT,
        [],
        [FarmOutput("T8_MILK", "Leite", 7, 11, 1.0, 900)],
        TAXAS,
        CICLO_FAZENDA,
        focus_cost=0,
    )
    assert economia.known is True
    assert economia.profit_per_focus is None
    assert economia.focus_per_day is None


def test_faixa_de_colheita_usa_a_media():
    """`3-6` vale 4,5 — não 3 e não 6."""
    economia = compute_farm_cycle(
        PlanKind.CROP, [semente(0 + 1)], [colheita(preco=100, minimo=3, maximo=6)],
        TAXAS, CICLO_FAZENDA,
    )
    assert economia.gross_revenue == pytest.approx(4.5 * 100, abs=0.01)


def test_chance_menor_que_um_reduz_o_valor_esperado():
    saida = FarmOutput("T3_FARM_OX_BABY", "Cria", 1, 1, 0.84, 1000)
    assert saida.expected_amount == pytest.approx(0.84)


def test_semente_que_volta_nao_paga_imposto_de_venda():
    """Ela é replantada, não vendida. Imposto ali seria taxa inventada."""
    vendida = compute_farm_cycle(
        PlanKind.CROP,
        [semente(1000)],
        [
            colheita(500),
            FarmOutput("T1_FARM_CARROT_SEED", "Semente", 1, 1, 1.0, 1000, primary=False),
        ],
        TAXAS, CICLO_FAZENDA,
    )
    replantada = compute_farm_cycle(
        PlanKind.CROP,
        [semente(1000)],
        [
            colheita(500),
            FarmOutput(
                "T1_FARM_CARROT_SEED", "Semente", 1, 1, 1.0, 1000, primary=False, taxed=False
            ),
        ],
        TAXAS, CICLO_FAZENDA,
    )
    assert replantada.profit_per_cycle > vendida.profit_per_cycle


def test_insumo_sem_cotacao_derruba_o_ciclo():
    """Custo parcial não é custo menor — é custo desconhecido."""
    economia = compute_farm_cycle(
        PlanKind.CROP, [semente(None)], [colheita()], TAXAS, CICLO_FAZENDA
    )
    assert economia.known is False
    assert "T1_FARM_CARROT_SEED" in economia.reason


def test_saida_secundaria_sem_cotacao_nao_derruba_mas_e_listada():
    """A minhoca que cai a 10% não vale invalidar a colheita inteira.

    Ela sai da receita e o nome fica na resposta: o lucro está abaixo do real,
    e quem lê precisa poder saber disso.
    """
    economia = compute_farm_cycle(
        PlanKind.CROP,
        [semente()],
        [colheita(), FarmOutput("T1_WORM", "Minhoca", 1, 1, 0.1, None, primary=False)],
        TAXAS, CICLO_FAZENDA,
    )
    assert economia.known is True
    assert economia.outputs_without_price == ["T1_WORM"]


def test_saida_principal_sem_cotacao_derruba_o_ciclo():
    economia = compute_farm_cycle(
        PlanKind.CROP, [semente()], [colheita(preco=None)], TAXAS, CICLO_FAZENDA
    )
    assert economia.known is False
    assert "T1_CARROT" in economia.reason


def test_sem_taxas_o_lucro_e_unknown():
    """Nunca calcular com taxa zero: otimista aqui é recomendar prejuízo."""
    economia = compute_farm_cycle(
        PlanKind.CROP, [semente()], [colheita()], SEM_TAXAS, CICLO_FAZENDA
    )
    assert economia.known is False
    assert "taxas não configuradas" in economia.reason


def test_ciclo_sem_duracao_e_unknown():
    """Sem tempo não há prata por dia, e prata por dia é o produto desta tela."""
    economia = compute_farm_cycle(PlanKind.CROP, [semente()], [colheita()], TAXAS, 0)
    assert economia.known is False


def test_per_day_converte_na_direcao_certa():
    assert per_day(100, DAY_SECONDS) == pytest.approx(100)
    assert per_day(100, DAY_SECONDS // 2) == pytest.approx(200)
    assert per_day(100, DAY_SECONDS * 2) == pytest.approx(50)
    assert per_day(None, DAY_SECONDS) is None
