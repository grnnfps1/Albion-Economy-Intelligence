"""Política do preço manual: quando ele vence o coletado.

O repositório entrega tudo que o usuário informou. Aqui fica a decisão, que tem
duas partes e as duas importam:

1. **Onde houver preço manual, ele vence.** O usuário está com o jogo aberto; a
   coleta é comunitária e pode ser de horas atrás.
2. **Preço manual também envelhece.** Passado o limite de frescor ele deixa de
   valer e o coletado volta. Um número digitado há três dias é tão perigoso
   quanto uma cotação de três dias — pior, porque parece autoridade.

O segundo ponto é o que separa isto de uma sobrescrita permanente. Não existe
preço imortal porque foi digitado.

`kind` é nomeado pela consequência, como os rótulos da interface:

    COMPRA  o que você paga     -> sell_price_min
    VENDA   o que você recebe   -> buy_price_max
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.manual_price import KIND_BUY, KIND_SELL
from app.repositories import manual_prices as manual_repo

# Qual campo de `market_prices` cada ponta sobrescreve.
FIELD_BY_KIND = {KIND_BUY: "sell_price_min", KIND_SELL: "buy_price_max"}


@dataclass(frozen=True)
class ManualQuote:
    """Um preço informado, com a idade que a tela precisa mostrar."""

    price: int
    informed_at: datetime
    age_seconds: int
    kind: str
    is_stale: bool
    """True quando passou do limite de frescor. Nesse caso **não** vence."""

    @property
    def applies(self) -> bool:
        return not self.is_stale


@dataclass(frozen=True)
class ManualPriceOverlay:
    """O conjunto de sobrescritas de um usuário, já datado.

    Sem usuário logado o overlay fica vazio e tudo se comporta como antes —
    é o modo de desenvolvimento local, onde `SESSION_SECRET` não está definido
    e a aplicação roda aberta.
    """

    quotes: dict[tuple[str, str, int, str], ManualQuote] = field(default_factory=dict)
    max_age_seconds: int = 21_600

    @property
    def empty(self) -> bool:
        return not self.quotes

    def quote(
        self, item: str, location: str, quality: int, kind: str
    ) -> ManualQuote | None:
        """A sobrescrita daquela ponta, velha ou não.

        Devolve mesmo a velha de propósito: a tela precisa poder dizer "existe
        um preço manual aqui, mas ele expirou", em vez de simplesmente ignorar
        e deixar o usuário achando que informou errado.
        """
        return self.quotes.get((item, location, quality, kind))

    def price_of(
        self, item: str, location: str, quality: int, kind: str
    ) -> int | None:
        """O preço que vence, ou `None` quando não há sobrescrita aplicável."""
        cotacao = self.quote(item, location, quality, kind)
        return cotacao.price if cotacao is not None and cotacao.applies else None

    def buy_price(self, item: str, location: str, quality: int = 1) -> int | None:
        """O que você paga — sobrescreve `sell_price_min`."""
        return self.price_of(item, location, quality, KIND_BUY)

    def sell_price(self, item: str, location: str, quality: int = 1) -> int | None:
        """O que você recebe — sobrescreve `buy_price_max`."""
        return self.price_of(item, location, quality, KIND_SELL)


async def load_manual_overlay(
    session: AsyncSession,
    user_id: str | None,
    server_code: str,
    max_age_seconds: int | None = None,
    now: datetime | None = None,
) -> ManualPriceOverlay:
    if max_age_seconds is None:
        max_age_seconds = get_settings().freshness_stale_seconds
    agora = now or datetime.now(UTC)

    cruas = await manual_repo.load_overrides(session, user_id, server_code)
    cotacoes: dict[tuple[str, str, int, str], ManualQuote] = {}
    for (item, slug, quality, kind), (preco, informado_em) in cruas.items():
        idade = max(0, int((agora - informado_em).total_seconds()))
        cotacoes[(item, slug, quality, kind)] = ManualQuote(
            price=preco,
            informed_at=informado_em,
            age_seconds=idade,
            kind=kind,
            is_stale=idade > max_age_seconds,
        )

    return ManualPriceOverlay(quotes=cotacoes, max_age_seconds=max_age_seconds)
