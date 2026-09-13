from pydantic import BaseModel, ConfigDict, Field


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    unique_name: str = Field(description="Id técnico do Albion. É a chave usada nas consultas.")
    base_name: str
    tier: int | None = Field(description="NULL quando o dump não informa tier para o item.")
    enchantment: int
    subcategory_code: str | None
    display_name_en: str | None
    display_name_pt: str | None
    weight: float | None
    max_quality: int | None
    is_tracked: bool = Field(description="true quando os collectors varrem este item.")
    icon_url: str | None = Field(
        default=None,
        description="Render oficial do jogo. Derivado do unique_name, não armazenado.",
    )


class ItemPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ItemOut]


class ServerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    display_name: str


class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    aodp_name: str
    display_name: str
    kind: str


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    display_name: str


class CatalogCounts(BaseModel):
    total: int
    tracked: int


class MetaResponse(BaseModel):
    servers: list[ServerOut]
    locations: list[LocationOut]
    categories: list[CategoryOut]
    tiers: list[int]
    enchantments: list[int]
    qualities: list[int]
    catalog: CatalogCounts
    data_source: str
    data_source_note: str
