import pytest
from pydantic import ValidationError

from app.core.config import Environment, Settings


def test_cors_origins_aceita_lista_separada_por_virgula():
    settings = Settings(cors_origins="http://a.com, http://b.com")
    assert settings.cors_origins == ["http://a.com", "http://b.com"]


def test_mock_data_proibido_em_producao():
    """Requisito 44: dado mock nunca pode ser servido como real."""
    with pytest.raises(ValidationError):
        Settings(environment="production", use_mock_data=True)


def test_mock_data_permitido_em_desenvolvimento():
    settings = Settings(environment="development", use_mock_data=True)
    assert settings.use_mock_data is True
    assert settings.is_production is False


def test_base_url_por_servidor(settings: Settings):
    assert settings.aodp_base_url("west") == "https://west.albion-online-data.com"
    assert settings.aodp_base_url("east") == "https://east.albion-online-data.com"
    assert settings.aodp_base_url("europe") == "https://europe.albion-online-data.com"


def test_servidor_desconhecido_falha_alto(settings: Settings):
    with pytest.raises(ValueError, match="servidor desconhecido"):
        settings.aodp_base_url("brazil")


def test_environment_producao():
    assert Settings(environment="production").environment is Environment.PRODUCTION
