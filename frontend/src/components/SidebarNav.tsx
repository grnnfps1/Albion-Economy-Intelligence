"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NavIcon } from "@/components/NavIcon";

type Item = { label: string; href: string; icon: string; soon?: string };
type Grupo = { titulo: string | null; itens: Item[] };

/**
 * Navegação agrupada por pergunta, não por ordem de implementação.
 *
 * Antes era uma lista corrida de onze itens. Onze escolhas no mesmo nível é o
 * mesmo que nenhuma hierarquia: o olho lê tudo toda vez. Os grupos respondem
 * "onde está o dinheiro" (Mercado), "como eu produzo" (Operações) e "a máquina
 * está de pé?" (Ferramentas).
 */
const GRUPOS: Grupo[] = [
  {
    titulo: null,
    itens: [{ label: "Painel", href: "/", icon: "painel" }],
  },
  {
    titulo: "Mercado",
    itens: [
      { label: "Mercado", href: "/market", icon: "mercado" },
      { label: "Histórico", href: "/market/history", icon: "historico" },
      { label: "Arbitragem", href: "/arbitrage", icon: "arbitragem" },
      { label: "Gold", href: "/gold", icon: "gold" },
    ],
  },
  {
    titulo: "Operações",
    itens: [
      { label: "Crafting", href: "/crafting", icon: "crafting" },
      { label: "Refinamento", href: "/refining", icon: "refino" },
      { label: "Agricultura", href: "/farming", icon: "agricultura" },
      { label: "Focus", href: "/focus", icon: "focus" },
    ],
  },
  {
    titulo: "Ferramentas",
    itens: [
      { label: "Pipeline", href: "/status", icon: "pipeline" },
      { label: "Transporte", href: "/transport", icon: "transporte", soon: "em breve" },
      { label: "Watchlist", href: "/watchlist", icon: "watchlist", soon: "em breve" },
    ],
  },
];

/**
 * `/` casa exato; o resto casa por prefixo, para que `/market/history` acenda
 * Histórico sem acender Mercado junto.
 */
function estaAtivo(href: string, atual: string): boolean {
  if (href === "/") return atual === "/";
  return atual === href || atual.startsWith(`${href}/`);
}

export function SidebarNav() {
  const atual = usePathname() ?? "/";

  return (
    <div className="flex flex-row gap-1 overflow-x-auto md:flex-col md:gap-4 md:overflow-visible">
      {GRUPOS.map((grupo, i) => (
        <div key={grupo.titulo ?? `topo-${i}`} className="contents md:block">
          {grupo.titulo && (
            <p className="lbl mb-1.5 hidden px-3 text-dim md:block">{grupo.titulo}</p>
          )}

          <ul className="contents md:flex md:flex-col md:gap-px">
            {grupo.itens.map((item) => {
              const ativo = !item.soon && estaAtivo(item.href, atual);

              // Item futuro não é link: seria mentira. Mas também não é só
              // texto apagado — apagado sem explicação parece defeito. A
              // etiqueta diz que existe e ainda não chegou.
              if (item.soon) {
                return (
                  <li key={item.href} className="shrink-0">
                    <span className="flex items-center gap-2.5 rounded-sm px-3 py-2 text-dim text-note">
                      <NavIcon name={item.icon} />
                      <span className="flex-1 truncate">{item.label}</span>
                      <span className="lbl hidden rounded-full border border-line px-1.5 py-px text-[8.5px] text-dim md:inline">
                        {item.soon}
                      </span>
                    </span>
                  </li>
                );
              }

              return (
                <li key={item.href} className="shrink-0">
                  <Link
                    href={item.href}
                    aria-current={ativo ? "page" : undefined}
                    className={`relative flex items-center gap-2.5 rounded-sm px-3 py-2 text-note transition-colors duration-150 ${
                      ativo
                        ? "bg-accent-dim font-medium text-accent-bright"
                        : "text-muted hover:bg-raised hover:text-body"
                    }`}
                  >
                    {/* A barra é o que se enxerga de canto de olho, antes de ler. */}
                    {ativo && (
                      <span
                        aria-hidden
                        className="absolute inset-y-1 left-0 w-[3px] rounded-r-full bg-accent"
                      />
                    )}
                    <NavIcon name={item.icon} />
                    <span className="truncate">{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}
