import { tierBorder, tierTint } from "@/lib/tiers";

/**
 * Ícone do item, servido pelo render oficial do jogo.
 *
 * `<img>` puro em vez de `next/image`: são dezenas por página vindas de um CDN
 * que já os entrega otimizados e com 24h de cache. Passar cada um pelo servidor
 * do Next trocaria um salto por dois.
 *
 * A moldura tem a cor do tier — convenção do próprio jogo. Numa lista densa o
 * olho separa T4 de T8 antes de ler o badge. O fundo repete a mesma cor a 10%,
 * que é o teto antes de começar a competir com o ícone.
 *
 * Era o único componente duplicado do projeto: existiam dois ItemIcon com mapas
 * de tier diferentes, e um deles pintava T3 com a cor de lucro. Agora é este, e
 * a cor vem de `lib/tiers`.
 */
export function ItemIcon({
  url,
  alt,
  tier,
  quantity,
  size = 46,
}: {
  url: string | null;
  alt: string;
  tier?: number | null;
  quantity?: number;
  size?: number;
}) {
  return (
    <span
      className={`relative grid shrink-0 place-items-center overflow-hidden rounded border ${tierBorder(
        tier,
      )} ${tierTint(tier)}`}
      style={{ width: size, height: size }}
    >
      {url ? (
        // O CDN pode não ter o ícone de um item novo. Falhar em silêncio é
        // melhor que um quadrado quebrado repetido na lista inteira.
        <img
          src={url}
          alt={alt}
          loading="lazy"
          decoding="async"
          width={size}
          height={size}
          className="size-full object-contain"
        />
      ) : (
        <span className="figure text-dim text-micro">?</span>
      )}

      {quantity !== undefined && (
        <span className="figure absolute right-px bottom-0 rounded-tl bg-sunken/90 px-0.5 text-body text-micro">
          {quantity}
        </span>
      )}
    </span>
  );
}
