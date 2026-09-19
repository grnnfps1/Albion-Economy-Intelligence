"""Preço informado à mão pelo usuário.

Cotação comunitária fica velha. Mercado pouco visitado pode não ter cotação
nenhuma, e quem está com o jogo aberto sabe o preço melhor do que a coleta.
Esta tabela é a saída: o usuário informa o preço que está vendo, e ele vence o
coletado.

## `kind` é onde a regra 7 morde

Comprar e vender são preços diferentes, e o nome do campo no AODP esconde isso.
A tabela usa a **consequência** como nome, que é a mesma regra da interface:

- `COMPRA` — o que você **paga** para levar o item. Sobrescreve
  `sell_price_min`, a ordem de venda mais barata.
- `VENDA` — o que você **recebe** ao vender na hora. Sobrescreve
  `buy_price_max`, a ordem de compra mais alta.

Chamar os dois de "preço" e deixar o usuário adivinhar inverteria o sinal do
lucro na metade dos casos.

## Preço manual também envelhece

Um preço manual de três dias atrás é tão perigoso quanto uma cotação de três
dias atrás — pior, porque parece autoridade. `created_at` é a idade exibida, e
acima do limite de frescor o preço manual **deixa de valer**, igual ao coletado.
Não existe preço imortal porque foi digitado.

## `user_id` é o `discord_id`

Não há tabela de contas ainda. A fonte da verdade do acesso é o Discord
(`middleware.ts`), e o id que a sessão carrega é o que identifica quem informou.
Quando contas existirem, esta coluna vira FK sem mudar a semântica.
"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin

# Os dois valores de `kind`. Nomeados pela consequência, não pelo campo da API.
KIND_BUY = "COMPRA"
KIND_SELL = "VENDA"
KINDS = (KIND_BUY, KIND_SELL)


class ManualPrice(Base, TimestampMixin):
    __tablename__ = "manual_prices"
    __table_args__ = (
        # Um preço por (usuário, servidor, local, item, qualidade, tipo).
        # Informar de novo atualiza, e atualizar renova a idade -- que é o
        # comportamento certo: o usuário acabou de olhar o mercado.
        UniqueConstraint(
            "user_id", "server_id", "location_id", "item_id", "quality", "kind",
            name="uq_manual_prices_chave",
        ),
        CheckConstraint("quality BETWEEN 1 AND 5", name="ck_manual_prices_quality"),
        # Zero não é preço, é ausência -- e ausência se apaga a linha, não se
        # grava. É a regra 1 aplicada à entrada manual.
        CheckConstraint("price > 0", name="ck_manual_prices_price_positivo"),
        CheckConstraint(
            "kind IN ('COMPRA', 'VENDA')", name="ck_manual_prices_kind"
        ),
        Index("ix_manual_prices_lookup", "user_id", "server_id", "item_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # `discord_id` da sessão. String porque o id do Discord é um snowflake de 64
    # bits que chega como texto e não se faz aritmética com ele.
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)

    server_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    quality: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
