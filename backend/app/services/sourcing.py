"""Onde comprar cada material: a política de escolha de cidade.

`calculations/` recebe número e devolve número. *Em qual cidade* comprar cada
material não é fórmula -- depende de quais cidades estão ativas, de qual cotação
ainda é confiável e de quanto espalhamento a operação aceita. Por isso a decisão
mora aqui, no serviço, e a função de cálculo continua recebendo só o preço.

Quatro regras que este módulo materializa:

- **Preço velho não entra na escolha.** Comprar mais barato num preço de ontem é
  pior que comprar caro num preço de agora: a ordem que justificava o desvio
  provavelmente já foi consumida.
- **Desviar nunca pode sair mais caro.** Se a única cotação fresca de outra
  cidade está acima da cotação da cidade base, a base continua sendo a resposta
  -- mesmo que a dela esteja velha. O modo MAIS_BARATO não pode piorar o custo.
- **Empate fica na cidade base.** Uma segunda cidade só se paga quando economiza
  de fato; empate com viagem é prejuízo.
- **Black Market fora.** Como *destino de venda* ele foi validado (fase 13), mas
  comprar material lá não foi medido — e é de compra que este módulo trata.
- **Preço manual vence o coletado.** Quem está com o jogo aberto sabe melhor
  que a coleta comunitária — mas o preço manual entra com a idade de quando foi
  informado e envelhece igual, então ele também perde a disputa quando fica
  velho (fase 17).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.freshness import data_age_seconds
from app.models.manual_price import KIND_BUY
from app.repositories import market as market_repo
from app.repositories.reference import list_locations
from app.services.manual_price_service import ManualPriceOverlay

BLACK_MARKET = "black_market"


class SourcingMode(StrEnum):
    SINGLE_CITY = "CIDADE_UNICA"
    """Todo material na cidade base. É o padrão e o comportamento histórico."""

    CHEAPEST = "MAIS_BARATO"
    """Cada material na cidade ativa mais barata, entre as cotações frescas."""

    COMPARE = "COMPARAR"
    """Calcula os dois roteiros e devolve a diferença."""

    @property
    def spreads(self) -> bool:
        """Modos que permitem comprar fora da cidade base."""
        return self is not SourcingMode.SINGLE_CITY

    @property
    def compares(self) -> bool:
        """Modos que precisam do roteiro de cidade única para comparar."""
        return self is not SourcingMode.SINGLE_CITY


@dataclass(frozen=True)
class Quote:
    """Uma cotação de compra: preço de venda mínimo de um item numa cidade."""

    location_slug: str
    location_name: str
    unit_price: int | None
    age_seconds: int | None
    is_manual: bool = False
    """True quando o preço veio do usuário e não da coleta.

    A idade continua sendo a idade: de quando ele informou. Preço manual velho
    é tão perigoso quanto cotação velha, e cai fora da escolha pela mesma regra.
    """

    @property
    def usable(self) -> bool:
        """Ausência de ordem é `None`, nunca 0 -- e `None` não é cotação."""
        return self.unit_price is not None


@dataclass(frozen=True)
class Choice:
    """Onde comprar um material, e o que isso muda em relação à cidade base."""

    quote: Quote | None
    base: Quote | None

    @property
    def known(self) -> bool:
        return self.quote is not None and self.quote.usable

    @property
    def unit_price(self) -> int | None:
        return self.quote.unit_price if self.quote is not None else None

    @property
    def is_alternate(self) -> bool:
        """A compra sai da cidade base?"""
        if self.quote is None:
            return False
        if self.base is None:
            # A base não tem cotação: a rota alternativa é o único jeito.
            return True
        return self.quote.location_slug != self.base.location_slug

    @property
    def savings_per_unit(self) -> float | None:
        """Quanto a escolha economiza por unidade contra a cidade base.

        `None` quando a base não tem cotação: aí não há o que comparar -- a
        cidade única simplesmente não conseguiria fazer este craft.
        """
        if self.base is None or not self.base.usable or not self.known:
            return None
        return float(self.base.unit_price - self.quote.unit_price)


@dataclass(frozen=True)
class CityQuote:
    """Uma cotação na lista do balão: cidade, preço, idade e se conta."""

    location_slug: str
    location_name: str
    unit_price: int
    age_seconds: int | None
    is_fresh: bool
    is_manual: bool
    is_chosen: bool


@dataclass(frozen=True)
class PriceRange:
    """O intervalo de preço de um material entre as cidades consultadas.

    Existe porque a tela mostrava só o preço **usado**, e com isso o usuário não
    tinha como saber se a escolha economizou muito ou se foi indiferente.
    Intervalo grande diz que vale a viagem; intervalo pequeno diz que comprar
    tudo numa cidade só custa quase nada — que é a decisão que `cities_involved`
    já sinalizava sem o número que a justifica.

    ## Só cotação fresca entra

    Mesma regra que governa a escolha (fase 11). Incluir cotação velha faria o
    intervalo parecer maior do que a decisão real, e o "maior preço" seria
    sempre a cidade que ninguém visita — um espalhamento que não existe para
    quem for comprar hoje.

    ## Uma cotação só não é intervalo

    É **falta de alternativa**, e muda a confiança no número: não há com o que
    comparar, e o preço não foi validado por nenhum outro mercado. Por isso
    `comparable` é falso com menos de duas cidades frescas, e a tela diz isso
    em vez de mostrar um intervalo de zero, que pareceria "todas as cidades
    cobram igual".
    """

    cities: list[CityQuote]
    """Todas as cidades com cotação utilizável, da mais barata para a mais cara."""

    min_price: int | None = None
    max_price: int | None = None
    fresh_city_count: int = 0

    @property
    def comparable(self) -> bool:
        return self.fresh_city_count >= 2 and self.min_price is not None

    @property
    def spread(self) -> int | None:
        if not self.comparable:
            return None
        return self.max_price - self.min_price

    @property
    def spread_pct(self) -> float | None:
        """Sobre o menor preço: "quanto a mais custa a cidade cara"."""
        if not self.comparable or not self.min_price:
            return None
        return round((self.max_price - self.min_price) / self.min_price * 100, 1)


class MaterialSourcing:
    """Decide, material a material, em qual cidade comprar.

    Recebe as cotações já carregadas para não esconder consulta atrás de um
    atributo: quem constrói sabe quantas cidades pediu ao banco.
    """

    def __init__(
        self,
        mode: SourcingMode,
        base_slug: str,
        quotes: Mapping[str, Sequence[Quote]],
        max_age_seconds: int,
    ) -> None:
        self.mode = mode
        self.base_slug = base_slug
        self.max_age_seconds = max_age_seconds
        self._quotes = quotes

    def _fresh(self, quote: Quote) -> bool:
        # Cotação sem data tem idade desconhecida, e idade desconhecida não
        # autoriza desvio de cidade.
        return quote.age_seconds is not None and quote.age_seconds <= self.max_age_seconds

    def base_quote(self, unique_name: str) -> Quote | None:
        return next(
            (
                q
                for q in self._quotes.get(unique_name, ())
                if q.location_slug == self.base_slug and q.usable
            ),
            None,
        )

    def choose(self, unique_name: str) -> Choice:
        base = self.base_quote(unique_name)
        if not self.mode.spreads:
            return Choice(quote=base, base=base)

        frescas = [q for q in self._quotes.get(unique_name, ()) if q.usable and self._fresh(q)]
        if not frescas:
            # Nada fresco em lugar nenhum: sobra a base, com a idade que tiver.
            return Choice(quote=base, base=base)

        # Empate escolhe a cidade base; depois disso, ordem alfabética para o
        # resultado não depender da ordem em que o banco devolveu as linhas.
        melhor = min(
            frescas,
            key=lambda q: (q.unit_price, q.location_slug != self.base_slug, q.location_slug),
        )
        if base is not None and base.unit_price <= melhor.unit_price:
            return Choice(quote=base, base=base)
        return Choice(quote=melhor, base=base)

    def range_of(self, unique_name: str) -> PriceRange:
        """Intervalo entre as cidades consultadas, e a lista para o balão.

        A lista traz **todas** as cotações utilizáveis, inclusive as velhas,
        porque o balão é onde o detalhe cabe e ver que Thetford tem preço de
        três dias atrás é informação. O intervalo, esse, sai só das frescas.
        """
        usaveis = [q for q in self._quotes.get(unique_name, ()) if q.usable]
        if not usaveis:
            return PriceRange(cities=[])

        escolhida = self.choose(unique_name).quote
        slug_escolhido = escolhida.location_slug if escolhida is not None else None

        cidades = sorted(
            (
                CityQuote(
                    location_slug=q.location_slug,
                    location_name=q.location_name,
                    unit_price=q.unit_price,
                    age_seconds=q.age_seconds,
                    is_fresh=self._fresh(q),
                    is_manual=q.is_manual,
                    is_chosen=q.location_slug == slug_escolhido,
                )
                for q in usaveis
            ),
            key=lambda c: (c.unit_price, c.location_slug),
        )

        frescas = [c for c in cidades if c.is_fresh]
        if len(frescas) < 2:
            return PriceRange(cities=cidades, fresh_city_count=len(frescas))

        return PriceRange(
            cities=cidades,
            min_price=frescas[0].unit_price,
            max_price=frescas[-1].unit_price,
            fresh_city_count=len(frescas),
        )

    def price_of(self, unique_name: str) -> int | None:
        """Preço da cidade escolhida. Assinatura de `market_price` da cadeia."""
        return self.choose(unique_name).unit_price

    def base_price_of(self, unique_name: str) -> int | None:
        """Preço da cidade base. O roteiro de comparação usa este."""
        quote = self.base_quote(unique_name)
        return quote.unit_price if quote is not None else None

    def single_city(self) -> "MaterialSourcing":
        """O mesmo conjunto de cotações, restrito à cidade base."""
        return MaterialSourcing(
            SourcingMode.SINGLE_CITY, self.base_slug, self._quotes, self.max_age_seconds
        )


async def load_material_sourcing(
    session: AsyncSession,
    *,
    server_code: str,
    item_unique_names: Sequence[str],
    base_slug: str,
    mode: SourcingMode,
    max_age_seconds: int,
    now: datetime,
    manual: "ManualPriceOverlay | None" = None,
) -> MaterialSourcing:
    """Carrega as cotações de todas as cidades candidatas e monta a política.

    **Isto mudou.** Antes, em CIDADE_UNICA consultava-se só a cidade base, com a
    justificativa de que o modo padrão não podia ficar mais caro em banco por um
    recurso que ele não usava. A premissa deixou de valer: o modo padrão agora
    *usa* as outras cidades — não para escolher, mas para **informar** o
    intervalo de preço (`range_of`). Sem as outras cotações, a tela não tem como
    dizer se a escolha economizou muito ou foi indiferente.

    `choose()` continua restrito pelo modo: em CIDADE_UNICA a compra segue sendo
    na base, aconteça o que acontecer nas outras. O que se ganhou foi
    informação, não comportamento.
    """
    cidades = [
        local.slug
        for local in await list_locations(session, only_active=True)
        if local.kind != BLACK_MARKET
    ]
    if base_slug not in cidades:
        cidades.append(base_slug)

    linhas = await market_repo.sell_quotes_by_city(
        session, server_code, list(item_unique_names), cidades
    )

    nomes_de_cidade = {slug: display for _n, slug, display, _p, _d in linhas}

    quotes: dict[str, list[Quote]] = {}
    for nome, slug, display, preco, data in linhas:
        # Preço manual de COMPRA sobrescreve a ordem de venda mais barata: é
        # literalmente o mesmo número — o que você paga.
        manual_quote = (
            None if manual is None else manual.quote(nome, slug, 1, KIND_BUY)
        )
        if manual_quote is not None:
            quotes.setdefault(nome, []).append(
                Quote(
                    location_slug=slug,
                    location_name=display,
                    unit_price=manual_quote.price,
                    age_seconds=manual_quote.age_seconds,
                    is_manual=True,
                )
            )
            continue

        quotes.setdefault(nome, []).append(
            Quote(
                location_slug=slug,
                location_name=display,
                unit_price=preco,
                age_seconds=data_age_seconds(data, now),
            )
        )

    # Preço manual numa cidade onde a coleta não tem nada é o caso que mais
    # justifica a funcionalidade: mercado pouco visitado, sem cotação nenhuma.
    # Sem este bloco ele seria ignorado justamente ali.
    if manual is not None:
        existentes = {
            (nome, q.location_slug) for nome, lista in quotes.items() for q in lista
        }
        for (nome, slug, quality, kind), cotacao in manual.quotes.items():
            if kind != KIND_BUY or quality != 1:
                continue
            if nome not in set(item_unique_names) or slug not in cidades:
                continue
            if (nome, slug) in existentes:
                continue
            quotes.setdefault(nome, []).append(
                Quote(
                    location_slug=slug,
                    location_name=nomes_de_cidade.get(slug, slug),
                    unit_price=cotacao.price,
                    age_seconds=cotacao.age_seconds,
                    is_manual=True,
                )
            )

    return MaterialSourcing(mode, base_slug, quotes, max_age_seconds)
