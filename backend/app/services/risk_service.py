"""Risco de rota: resolução da preferência e classificação da zona.

Mesma divisão do resto do projeto: `calculations/risk.py` é a fórmula pura e
aqui fica a política — de onde vem a probabilidade, quais locais contam como
zona aberta, e o que fazer quando o par não está na tabela.

A precedência é a mesma das taxas, com **uma diferença deliberada no fundo**:

```
parâmetro da requisição  →  config_parameters  →  0
```

Taxa ausente vira `UNKNOWN` porque calcular sem imposto inventa lucro. Risco
ausente vira **zero**, porque zero aqui não é chute: é dizer "não estou
modelando perda", e o resultado ajustado sai idêntico ao bruto, onde qualquer um
vê. O contrário — travar a tela inteira porque ninguém mediu quantas vezes já
perdeu carga — esconderia o produto por um número que só o usuário tem.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.calculations.risk import RiskAdjusted, RiskProfile, Zone, classify_zone
from app.repositories import settings_repo
from app.repositories.transport_repo import open_world_slugs, zones_by_pair
from app.schemas.risk import RiskOut, RiskUsed

BLUE_KEY = "risk.loss_probability.blue"
RED_KEY = "risk.loss_probability.red_black"

ZONE_LABELS = {
    Zone.LOCAL: "mesma cidade",
    Zone.BLUE: "zona azul",
    Zone.RED_BLACK: "vermelha/preta",
}


def risk_out(risco: RiskAdjusted) -> RiskOut:
    """Traduz o resultado puro para a resposta, com o rótulo que a tela usa."""
    zona = Zone(risco.zone)
    return RiskOut(
        zone=risco.zone,
        zone_label=ZONE_LABELS[zona],
        crosses_open_world=zona is Zone.RED_BLACK,
        loss_probability=risco.loss_probability,
        gross_profit=risco.gross_profit,
        investment=risco.investment,
        expected_profit=risco.expected_profit,
        expected_loss=risco.expected_loss,
        survives_risk=risco.survives_risk,
    )


@dataclass
class RouteZones:
    """Zona de cada par, com a regra genérica como rede de segurança.

    A tabela é a fonte: ela permite corrigir um par à mão (`is_manual`). Quando
    o par não está lá — local novo, seed não rodado — a classificação cai na
    mesma regra que gerou a tabela, em vez de sumir com a linha.
    """

    tabela: dict[tuple[str, str], str]
    zona_aberta: frozenset[str]

    def of(self, origin_slug: str, destination_slug: str) -> Zone:
        if origin_slug == destination_slug:
            return Zone.LOCAL
        gravada = self.tabela.get((origin_slug, destination_slug))
        if gravada is not None:
            return Zone(gravada)
        return classify_zone(origin_slug, destination_slug, self.zona_aberta)


async def load_route_zones(session: AsyncSession) -> RouteZones:
    return RouteZones(
        tabela=await zones_by_pair(session),
        zona_aberta=await open_world_slugs(session),
    )


async def resolve_risk(
    session: AsyncSession,
    loss_pct_blue: float | None,
    loss_pct_red_black: float | None,
) -> tuple[RiskProfile, RiskUsed]:
    origem = "usuario"

    if loss_pct_blue is None or loss_pct_red_black is None:
        configurado = await settings_repo.get_values(session, [BLUE_KEY, RED_KEY])
        if loss_pct_blue is None:
            loss_pct_blue = configurado.get(BLUE_KEY)
            origem = "config"
        if loss_pct_red_black is None:
            loss_pct_red_black = configurado.get(RED_KEY)
            origem = "config"

    # Só aqui o `None` vira zero, e a resposta diz que virou.
    perfil = RiskProfile(
        loss_pct_blue=float(loss_pct_blue or 0.0),
        loss_pct_red_black=float(loss_pct_red_black or 0.0),
    )

    return perfil, RiskUsed(
        loss_pct_blue=perfil.loss_pct_blue,
        loss_pct_red_black=perfil.loss_pct_red_black,
        source=origem if perfil.modelled else "padrao_zero",
        modelled=perfil.modelled,
    )
