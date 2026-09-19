"use client";

import { useState } from "react";

/**
 * Copiar o nome de um item para colar na busca do mercado, dentro do jogo.
 *
 * Quatro decisões que vieram da iteração e não são cosméticas:
 *
 * 1. **Visível sempre**, não só no hover. Um alvo que só aparece quando o mouse
 *    passa por cima não é descoberto por quem não sabe que existe.
 * 2. **Encostado no preço**, não na borda da célula. Com `margin-left:auto` ele
 *    ia para o fim da coluna e ficava longe do que copia.
 * 3. **Copia o nome por padrão**, porque é o que a busca do mercado no jogo
 *    entende. `alt+clique` copia o id técnico, para colar em outra ferramenta
 *    ou no Discord.
 * 4. **Nunca copia o id em silêncio.** A busca do jogo não encontra
 *    `T8_METALBAR`. Sem nome, o botão fica desabilitado e o título diz por quê
 *    — ver a nota abaixo.
 *
 * ## Por que desabilitar e não cair no inglês
 *
 * As duas opções foram medidas contra o catálogo real (19/09/2026). Entre os
 * **455 itens rastreados** — os únicos que chegam a estas telas —, 30 não têm
 * nome em português, e **os mesmos 30 também não têm nome em inglês**: são
 * templates de Liga de Cristal e um cristal de arena, que não são itens de
 * mercado. Ou seja, cair no inglês cobriria **zero** casos reais e deixaria o
 * botão copiando string vazia nos 30.
 *
 * Desabilitar é a opção que faz alguma coisa. Fica registrado que o fallback
 * para inglês foi considerado, medido e descartado por cobertura nula, e não
 * por preferência.
 */
export function CopyButton({
  name,
  id,
  className = "",
}: {
  /** Nome visual. `null` quando o dump não traz — aí o botão desabilita. */
  name: string | null;
  /** Id técnico do Albion. Vai no `alt+clique`. */
  id: string;
  className?: string;
}) {
  const [estado, setEstado] = useState<"ocioso" | "ok" | "erro">("ocioso");
  const indisponivel = !name;

  async function copiar(texto: string) {
    try {
      // `navigator.clipboard` exige contexto seguro. `http://localhost` conta
      // como seguro, mas um IP na rede local não — e é assim que muita gente
      // abre a ferramenta de outro computador. O fallback cobre esse caso.
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(texto);
      } else {
        const ta = document.createElement("textarea");
        ta.value = texto;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        ta.remove();
      }
      setEstado("ok");
    } catch {
      // Falhar calado faria o usuário clicar de novo achando que não pegou.
      setEstado("erro");
    }
    setTimeout(() => setEstado("ocioso"), 1200);
  }

  if (indisponivel) {
    return (
      <span
        aria-disabled="true"
        title={`Sem nome visual para ${id}. A busca do mercado no jogo não encontra o id técnico, então não há o que copiar.`}
        className={`shrink-0 cursor-not-allowed px-[2px] text-note leading-none text-line-strong ${className}`}
      >
        ⧉
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={(e) => copiar(e.altKey ? id : name)}
      title={`copiar «${name}»\nalt+clique copia ${id}`}
      aria-label={`copiar ${name}`}
      className={`shrink-0 cursor-pointer border-0 bg-transparent px-[2px] text-note leading-none transition-colors ${
        estado === "ok" ? "text-up" : estado === "erro" ? "text-down" : "text-dim hover:text-body"
      } ${className}`}
    >
      {estado === "ok" ? "✓" : estado === "erro" ? "✕" : "⧉"}
    </button>
  );
}
