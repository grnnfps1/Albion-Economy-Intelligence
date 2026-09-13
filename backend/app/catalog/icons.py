"""URL do ícone do item.

Fonte: serviço de render oficial do jogo, verificado na wiki em 2026-09-13.

    https://render.albiononline.com/v1/item/{identifier}.png?quality=N&size=N

O `identifier` é o `unique_name` literal — o sufixo `@1` de encantamento já vai
nele e o serviço entende. Nada precisa ser recomposto.

A URL é **derivada, não armazenada**: guardar 12 mil URLs em `items.icon_url`
criaria uma cópia que precisa ser migrada toda vez que o serviço mudar de host
ou de parâmetro. Derivar custa nada e nunca fica desatualizado.

As imagens são servidas direto ao browser pelo CDN da Sandbox. Não passam pelo
nosso backend: proxyá-las gastaria banda e latência sem benefício.
"""

RENDER_BASE = "https://render.albiononline.com/v1/item"

# Limites documentados pelo serviço.
MIN_SIZE, MAX_SIZE = 1, 217
MIN_QUALITY, MAX_QUALITY = 1, 5


def item_icon_url(unique_name: str, quality: int = 1, size: int = 64) -> str | None:
    """Devolve a URL, ou None quando o identificador não serve.

    Identificador vazio vira None em vez de uma URL quebrada: a UI sabe lidar
    com ausência de ícone, mas não com uma imagem que dá 404 em toda linha.
    """
    identifier = unique_name.strip()
    if not identifier:
        return None

    quality = min(max(quality, MIN_QUALITY), MAX_QUALITY)
    size = min(max(size, MIN_SIZE), MAX_SIZE)
    return f"{RENDER_BASE}/{identifier}.png?quality={quality}&size={size}"
