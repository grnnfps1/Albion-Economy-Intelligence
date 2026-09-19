import { CopyButton } from "@/components/sheet/CopyButton";
import { HoverTip } from "@/components/sheet/HoverTip";
import { ItemIcon } from "@/components/ui/ItemIcon";
import { formatSilver } from "@/lib/format";

/**
 * Um material, numa coluna só dele.
 *
 * A decisão de fundo: **uma coluna por material** em vez de todos empilhados
 * numa célula. Quem vem de planilha encontra o mesmo modelo mental, e comparar
 * o preço do mesmo material entre duas linhas vira uma leitura vertical em vez
 * de uma caça dentro de uma célula composta.
 *
 * Três detalhes que vieram da iteração:
 *
 * - **O nome só aparece no balão de hover.** Ele é longo e roubaria a largura
 *   das colunas de decisão, que são o motivo de a tela existir. Sem ele, porém,
 *   o ícone sozinho obriga a decorar arte — daí o balão, e não o `title`
 *   nativo, que demora quase um segundo e some ao mover o mouse.
 * - **O badge do ícone é a quantidade; o texto é o preço unitário.** Nada
 *   duplicado: repetir a quantidade nos dois gasta espaço e confunde.
 * - **O botão de copiar fica encostado no preço**, não na borda da célula, e
 *   visível sempre.
 */
export function MaterialCell({
  item,
  itemName,
  iconUrl,
  quantity,
  unitPrice,
  tier,
  locationName,
  isAlternateCity = false,
  tip,
}: {
  item: string;
  itemName: string | null;
  iconUrl: string | null;
  quantity: number;
  unitPrice: number | null;
  tier: number | null;
  locationName: string | null;
  isAlternateCity?: boolean;
  /** Texto do balão. Cai no nome do item quando não informado. */
  tip?: string;
}) {
  return (
    <td className="l">
      <HoverTip
        dica={tip ?? `${itemName ?? item} · ${item}`}
        className="flex min-w-0 items-center gap-1.5"
      >
        <ItemIcon
          url={iconUrl}
          alt={itemName ?? item}
          tier={tier}
          quantity={quantity}
          size={20}
        />
        <span className="min-w-0">
          <span className="flex items-center">
            <span className="figure">{formatSilver(unitPrice)}</span>
            <CopyButton name={itemName} id={item} />
          </span>
          <span
            className={`block truncate text-[9px] ${
              isAlternateCity ? "text-warn" : "text-dim"
            }`}
          >
            {locationName ?? "—"}
          </span>
        </span>
      </HoverTip>
    </td>
  );
}

/** Célula vazia, para receitas com menos materiais que o máximo da tabela. */
export function EmptyMaterialCell() {
  return <td className="l text-dim">—</td>;
}
