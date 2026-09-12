"""Parser do identificador de item.

Funções puras: entra string, sai estrutura. Sem I/O, sem banco -- é o que
permite validar as 12 mil variações reais do catálogo em teste sem rede.

Formatos observados em `formatted/items.txt` (fonte oficial):

    T4_PLANKS               base, sem encantamento
    T4_BAG@1                equipamento encantado
    T4_PLANKS_LEVEL1@1      recurso refinado encantado
    UNIQUE_HIDEOUT          item sem tier

Regra: o sufixo `@N` é a autoridade sobre o encantamento. O `_LEVELN` é como o
dump nomeia a variante e nem sempre acompanha todos os itens.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

_TIER_RE = re.compile(r"^T(\d)_")
_LEVEL_SUFFIX_RE = re.compile(r"_LEVEL\d+$")


@dataclass(frozen=True)
class ParsedItemName:
    unique_name: str
    """Identificador literal, exatamente como vem da fonte. É a chave lógica."""

    literal_base: str
    """Parte antes do `@`. Para `T4_PLANKS_LEVEL1@1`, é `T4_PLANKS_LEVEL1`."""

    dump_key_candidates: tuple[str, ...]
    """Chaves a tentar no dump completo, em ordem de preferência.

    `_LEVELN` quase sempre marca a variante encantada (`T4_PLANKS_LEVEL1` é o
    `T4_PLANKS` encantado), mas em alguns itens faz parte do nome de verdade --
    `T1_FISHSAUCE_LEVEL1`, `T1_FISHSAUCE_LEVEL2` e `T1_FISHSAUCE_LEVEL3` são
    itens distintos. Não dá para decidir só olhando a string: quem resolve é
    `resolve_base_name`, consultando o que existe no dump.
    """

    tier: int | None
    """None quando o identificador não codifica tier. Nunca chutar (requisito 52)."""

    enchantment: int


class InvalidItemName(ValueError):
    pass


def parse_item_name(unique_name: str) -> ParsedItemName:
    raw = unique_name.strip()
    if not raw:
        raise InvalidItemName("identificador vazio")

    enchantment = 0
    literal_base = raw

    if "@" in raw:
        literal_base, _, suffix = raw.partition("@")
        if not suffix.isdigit():
            raise InvalidItemName(f"encantamento não numérico em {raw!r}")
        enchantment = int(suffix)
        if not 0 <= enchantment <= 4:
            raise InvalidItemName(f"encantamento fora da faixa 0-4 em {raw!r}")
        if not literal_base:
            raise InvalidItemName(f"identificador sem nome base em {raw!r}")

    tier_match = _TIER_RE.match(raw)
    tier = int(tier_match.group(1)) if tier_match else None

    stripped = _LEVEL_SUFFIX_RE.sub("", literal_base)
    candidates = (stripped, literal_base) if stripped != literal_base else (literal_base,)

    return ParsedItemName(
        unique_name=raw,
        literal_base=literal_base,
        dump_key_candidates=candidates,
        tier=tier,
        enchantment=enchantment,
    )


def resolve_base_name(parsed: ParsedItemName, exists: "Callable[[str], bool]") -> str:
    """Escolhe a raiz do item consultando o que realmente existe no dump.

    Cai no `literal_base` quando nenhum candidato existe: melhor um agrupamento
    literal do que um grupo inventado.
    """
    for candidate in parsed.dump_key_candidates:
        if exists(candidate):
            return candidate
    return parsed.literal_base
