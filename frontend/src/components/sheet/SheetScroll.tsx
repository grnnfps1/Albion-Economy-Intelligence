"use client";

import { useEffect, useRef } from "react";

/**
 * O contêiner de rolagem da tabela, com a altura medida e não chutada.
 *
 * ## Por que existe
 *
 * `position: sticky` se resolve contra o **scrollport mais próximo**. Com a
 * tabela dentro de um `overflow-x: auto`, esse scrollport é o próprio div — que
 * tem a altura do conteúdo e portanto nunca rola na vertical. O `thead` ficava
 * `sticky` sem nada a que grudar: o cabeçalho sumia ao rolar a página, e o
 * defeito não aparecia no CSS, que estava correto.
 *
 * O conserto é dar altura ao contêiner, para que ele seja de verdade o
 * scrollport dos dois eixos.
 *
 * ## Por que medir em vez de calcular
 *
 * A altura disponível é `viewport − o que está acima da tabela`, e o que está
 * acima muda: o título quebra em duas linhas numa largura e em três noutra, a
 * tira de parâmetros some quando não há linhas, e o painel de preferências
 * abre e fecha. Um `calc(100dvh - 12rem)` acerta numa tela e erra em todas as
 * outras — e erra em silêncio, porque a tabela continua aparecendo.
 *
 * Aqui a distância do topo é lida do próprio elemento e reescrita quando algo
 * muda de tamanho. O número vive em uma variável CSS, num lugar só.
 */
export function SheetScroll({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const medir = () => {
      el.style.setProperty("--sheet-top", `${Math.round(el.getBoundingClientRect().top)}px`);
    };

    medir();
    // `ResizeObserver` no `body` pega o que muda **acima** da tabela: o painel
    // de preferências abrindo, o título rebobinando, a tira de parâmetros
    // aparecendo. Um listener de `resize` só pegaria a janela.
    const observador = new ResizeObserver(medir);
    observador.observe(document.body);
    window.addEventListener("scroll", medir, { passive: true });
    return () => {
      observador.disconnect();
      window.removeEventListener("scroll", medir);
    };
  }, []);

  return (
    <div ref={ref} className="sheet-scroll">
      {children}
    </div>
  );
}
