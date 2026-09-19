"""Entrada e saída de preço manual."""

from pydantic import BaseModel, Field

from app.models.manual_price import KIND_BUY, KIND_SELL


class ManualPriceIn(BaseModel):
    """O que o usuário informa.

    `kind` é nomeado pela consequência, não pelo campo da API: `COMPRA` é o que
    você paga e `VENDA` é o que você recebe. Chamar os dois de "preço" e deixar
    o usuário adivinhar inverteria o sinal do lucro na metade dos casos.
    """

    server: str = Field(default="west")
    location: str = Field(description="slug da cidade")
    item: str = Field(description="id técnico do Albion")
    quality: int = Field(default=1, ge=1, le=5)
    # Zero não é preço, é ausência — e ausência se remove, não se grava.
    price: int = Field(gt=0, description="prata por unidade")
    kind: str = Field(
        default=KIND_BUY,
        description=f"{KIND_BUY} (o que você paga) | {KIND_SELL} (o que você recebe)",
    )


class ManualPriceOut(BaseModel):
    server: str
    location: str
    location_name: str
    item: str
    item_name: str | None = None
    icon_url: str | None = None
    quality: int
    price: int
    kind: str
    informed_at: str
    age_seconds: int
    is_stale: bool = Field(
        description=(
            "True quando passou do limite de frescor. Nesse caso o preço manual "
            "deixa de vencer o coletado — não existe preço imortal porque foi "
            "digitado."
        )
    )


class ManualPriceList(BaseModel):
    server: str
    total: int
    max_age_seconds: int
    prices: list[ManualPriceOut]
