"""Montagem de lotes de requisição.

O AODP limita a URL a 4096 caracteres e pede que se combine muitos itens por
chamada. O lote é fechado pelo **comprimento da URL final**, não por contagem de
itens: `T8_2H_HOLYSTAFF_MORGANA@3` ocupa quase quatro vezes mais que `T4_BAG`, e
contar itens estoura ou desperdiça.

Funções puras -- dá para verificar o limite sem rede.
"""

from collections.abc import Iterable, Iterator
from urllib.parse import quote, urlencode


class ItemNameTooLong(ValueError):
    """Um único item não cabe na URL. Não há lote possível; falha alto."""


def build_url(base_url: str, path: str, item_names: Iterable[str], params: dict[str, str]) -> str:
    """Monta a URL exatamente como ela vai para a rede.

    O comprimento precisa ser medido no resultado codificado: `Fort Sterling`
    vira `Fort%20Sterling` e ocupa mais espaço do que aparenta.
    """
    joined = quote(",".join(item_names), safe=",@_")
    query = urlencode(params) if params else ""
    url = f"{base_url}{path.format(item_ids=joined)}"
    return f"{url}?{query}" if query else url


def batch_item_names(
    item_names: Iterable[str],
    base_url: str,
    path: str,
    params: dict[str, str],
    max_url_length: int,
) -> Iterator[list[str]]:
    """Divide os itens em lotes que caibam no limite de URL.

    Preserva a ordem de entrada: a coleta fica previsível e um lote que falhou
    pode ser reproduzido.
    """
    current: list[str] = []

    for name in item_names:
        candidate = [*current, name]
        if len(build_url(base_url, path, candidate, params)) <= max_url_length:
            current = candidate
            continue

        if not current:
            # Nem sozinho cabe: não adianta tentar de novo com menos itens.
            raise ItemNameTooLong(
                f"{name!r} não cabe em uma URL de {max_url_length} caracteres"
            )

        yield current
        current = [name]

        if len(build_url(base_url, path, current, params)) > max_url_length:
            raise ItemNameTooLong(
                f"{name!r} não cabe em uma URL de {max_url_length} caracteres"
            )

    if current:
        yield current
