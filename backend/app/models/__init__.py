"""Registro de modelos.

Importar tudo aqui garante que o autogenerate do Alembic enxergue as tabelas.
"""

from app.models.catalog import Item
from app.models.farming import Farmable, FarmableOutput
from app.models.market import GoldPrice, MarketHistory, MarketPrice
from app.models.observability import CollectorRun, RawResponse
from app.models.recipes import Recipe, RecipeMaterial
from app.models.reference import DataSource, ItemCategory, Location, Server
from app.models.settings import ConfigParameter

__all__ = [
    "CollectorRun",
    "ConfigParameter",
    "DataSource",
    "Farmable",
    "FarmableOutput",
    "GoldPrice",
    "Item",
    "ItemCategory",
    "Location",
    "MarketHistory",
    "MarketPrice",
    "RawResponse",
    "Recipe",
    "RecipeMaterial",
    "Server",
]
