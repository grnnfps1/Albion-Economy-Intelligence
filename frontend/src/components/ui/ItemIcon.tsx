const MOLDURA: Record<number, string> = {
  1: "border-t1", 2: "border-t2", 3: "border-t3", 4: "border-t4",
  5: "border-t5", 6: "border-t6", 7: "border-t7", 8: "border-t8",
};

/**
 * Ícone do item, servido pelo render oficial do jogo.
 *
 * `<img>` puro em vez de `next/image`: são dezenas por página vindas de um CDN
 * que já os entrega otimizados, e passar pelo servidor do Next deixaria mais
 * lento.
 *
 * A moldura tem a cor do tier — convenção do próprio jogo. Numa lista densa o
 * olho separa T4 de T8 antes de ler o badge.
 */
export function ItemIcon({
  url, alt, tier, quantity, size = 46,
}: {
  url: string | null;
  alt: string;
  tier?: number | null;
  quantity?: number;
  size?: number;
}) {
  return (
    <span
      className={`relative grid shrink-0 place-items-center overflow-hidden rounded border bg-sunken ${
        MOLDURA[tier ?? 0] ?? "border-line-strong"
      }`}
      style={{ width: size, height: size }}
    >
      {url && (
        <img
          src={url} alt={alt} loading="lazy" decoding="async"
          className="size-full object-contain"
        />
      )}
      {quantity !== undefined && (
        <span className="figure absolute right-px bottom-0 rounded-tl bg-sunken/90 px-[3px] text-[9px] text-body">
          {quantity}
        </span>
      )}
    </span>
  );
}
