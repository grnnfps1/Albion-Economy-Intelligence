from pydantic import BaseModel, Field


class RiskUsed(BaseModel):
    """As probabilidades que produziram o lucro ajustado.

    Vai na resposta pelo mesmo motivo que as taxas vão: sem isso, um lucro
    descontado em 15% não é auditável. E `modelled = false` é o estado normal —
    significa que ninguém informou risco e que o ajustado é igual ao bruto.
    """

    loss_pct_blue: float = 0.0
    loss_pct_red_black: float = 0.0
    source: str = Field(
        default="padrao_zero",
        description="'usuario', 'config' ou 'padrao_zero' quando ninguém informou.",
    )
    modelled: bool = False


class RiskOut(BaseModel):
    """Os dois números lado a lado, por operação.

    Nunca só o ajustado: um número que já vem descontado, sem o bruto ao lado,
    esconde de onde veio o desconto. E nunca só o bruto: numa rota de zona
    vermelha ele é a recomendação que quebra o jogador.
    """

    zone: str = Field(description="MESMA_CIDADE | AZUL | VERMELHA_PRETA")
    zone_label: str
    crosses_open_world: bool
    loss_probability: float

    gross_profit: float | None = None
    investment: float | None = None
    expected_profit: float | None = None
    expected_loss: float | None = Field(
        default=None, description="Quanto o risco tirou do lucro bruto."
    )
    survives_risk: bool = False
    """O lucro continua positivo depois do desconto?"""
