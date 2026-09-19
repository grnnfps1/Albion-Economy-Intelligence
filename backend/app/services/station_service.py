"""Política da taxa de estação: quanto custa, por item.

`calculations/station.py` tem a fórmula. Aqui fica o que ela não pode saber:
quanto o dono da estação cobra (configuração ou preferência) e qual é o
`item_value` de cada item (catálogo).

A precedência é a das **taxas de mercado**, não a da matriz de retorno:

    parâmetro da requisição  →  config_parameters  →  UNKNOWN

O motivo é o mesmo do imposto de venda. A prata por 100 de nutrição é escolha do
dono da estação e muda por cidade e por hora; o sistema não tem como saber qual
estação o usuário vai usar. Já a matriz de retorno depende de (cidade,
atividade, Focus) — coisas que o sistema sabe —, e por isso lá o valor primário é
o do sistema.
"""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.station import StationFee, station_fee_for
from app.repositories import settings_repo

FEE_KEY = "crafting.station_fee_per_100_nutrition"


@dataclass(frozen=True)
class StationFeePolicy:
    """A taxa em uso, já ligada ao catálogo.

    Existe para que os serviços não precisem carregar `item_value` item a item
    nem repetir a mesma aritmética em quatro lugares.
    """

    fee_per_100_nutrition: float | None
    item_value_of: Callable[[str], float | None]

    @property
    def known(self) -> bool:
        return self.fee_per_100_nutrition is not None

    def fee_of(self, unique_name: str, crafts: int = 1) -> StationFee:
        return station_fee_for(
            self.item_value_of(unique_name), self.fee_per_100_nutrition, crafts
        )

    def silver_of(self, unique_name: str, crafts: int = 1) -> float | None:
        """Só a prata, para quem já trata `None` como UNKNOWN.

        É esta que `chain.py` recebe como `station_fee_of`: a cadeia consulta
        por elo, porque cada elo paga a taxa do que ele próprio produz.
        """
        return self.fee_of(unique_name, crafts).silver

    def missing(self) -> list[str]:
        return [] if self.known else [FEE_KEY]


async def load_station_fee_policy(
    session: AsyncSession,
    item_value_of: Callable[[str], float | None],
    fee_per_100_nutrition: float | None = None,
) -> StationFeePolicy:
    """Resolve a taxa e devolve a política pronta.

    `fee_per_100_nutrition` vindo da requisição vence a configuração, que vence
    UNKNOWN — a mesma escada das taxas de mercado.
    """
    if fee_per_100_nutrition is None:
        fee_per_100_nutrition = await settings_repo.get_value(session, FEE_KEY)

    return StationFeePolicy(
        fee_per_100_nutrition=fee_per_100_nutrition,
        item_value_of=item_value_of,
    )


def item_value_lookup(catalogo: dict) -> Callable[[str], float | None]:
    """`unique_name -> item_value` a partir do dicionário de catálogo já carregado.

    Os serviços carregam o catálogo indexado por id; aqui ele vira índice por
    nome, que é a chave com que a cadeia e o motor de craft trabalham.
    """
    por_nome = {
        item.unique_name: (None if item.item_value is None else float(item.item_value))
        for item in catalogo.values()
    }
    return por_nome.get
