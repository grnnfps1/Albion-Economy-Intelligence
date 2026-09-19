"""Parâmetros de especialização, compartilhados pelas rotas.

Quatro rotas pedem os mesmos cinco campos; repetir a lista em cada uma
convidaria a divergirem.
"""
from app.services.specialization_service import DEFAULT_FAMILIES

# Uma linha por recurso em vez de item a item: a planilha faz item a item, mas
# isso seriam centenas de campos no formulário. A lista vive no serviço, que é
# quem a compara com o que vem da configuração.
SPEC_FAMILIES = DEFAULT_FAMILIES


def spec_levels_from(
    spec_leather: int, spec_cloth: int, spec_planks: int,
    spec_metalbar: int, spec_stoneblock: int,
) -> dict[str, int]:
    """Níveis informados, por família.

    Zero não é ausência aqui: significa "não especializado", e o custo em Focus
    sai igual ao do dump. A resposta carrega `assumes_zero_spec` para a tela
    poder dizer isso em vez de apresentar o número como se fosse do usuário.
    """
    return dict(
        zip(
            SPEC_FAMILIES,
            (spec_leather, spec_cloth, spec_planks, spec_metalbar, spec_stoneblock),
            strict=True,
        )
    )
