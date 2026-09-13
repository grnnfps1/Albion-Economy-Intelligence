/**
 * Ícone do item, servido pelo render oficial do jogo.
 *
 * `<img>` puro em vez de `next/image`: a otimização do Next faria cada ícone
 * passar pelo servidor, e são dezenas por página vindas de um CDN que já os
 * entrega otimizados. O ganho seria negativo.
 *
 * A moldura tem cor por tier — é a convenção do próprio jogo, e numa lista
 * densa o olho separa T4 de T8 antes de ler o badge.
 */
const MOLDURA: Record<number, string> = {
  1: "border-line",
  2: "border-line",
  3: "border-line-strong",
  4: "border-up/40",
  5: "border-down/40",
  6: "border-bridgewatch/50",
  7: "border-warn/50",
  8: "border-silver/40",
};

export function ItemIcon({
  url,
  alt,
  tier,
  quantity,
  size = 44,
}: {
  url: string | null;
  alt: string;
  tier?: number | null;
  quantity?: number;
  size?: number;
}) {
  const moldura = MOLDURA[tier ?? 0] ?? "border-line";

  return (
    <span
      className={`relative inline-flex shrink-0 items-center justify-center rounded-sm border bg-sunken ${moldura}`}
      style={{ width: size, height: size }}
    >
      {url ? (
        // O CDN pode não ter o ícone de um item novo. Falhar em silêncio é
        // melhor do que um quadrado quebrado repetido na lista inteira.
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
        <span className="figure text-[10px] text-line-strong">?</span>
      )}
      {quantity !== undefined && (
        <span className="figure absolute right-0 bottom-0 rounded-tl-sm bg-ink px-1 text-[10px] text-muted">
          {quantity}
        </span>
      )}
    </span>
  );
}
