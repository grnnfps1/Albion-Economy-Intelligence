"use client";

import { useEffect, useRef } from "react";

/**
 * O contêiner de rolagem da tabela, com a altura medida.
 *
 * ## Por que precisa de altura
 *
 * `position: sticky` se resolve contra o **scrollport mais próximo**, e
 * `overflow-x: auto` já torna este div o scrollport dos dois eixos — é regra do
 * CSS, não escolha. Sem altura definida ele nunca rola na vertical, e o `thead`
 * fica `sticky` sem nada a que grudar: o cabeçalho some junto com as linhas.
 *
 * ## Por que medir, e por que a fase 28 errou ao trocar isto por flexbox
 *
 * A fase 28 tirou a medição e deixou o flexbox dimensionar (`flex: 1` dentro de
 * uma coluna limitada à janela). A ideia era boa e a execução dependia de uma
 * corrente de cinco ancestrais todos com `min-height: 0` e altura definida —
 * qualquer elo frouxo e o resultado é uma tabela curta com espaço sobrando
 * abaixo, que foi exatamente o que apareceu. Corrente longa de CSS é frágil de
 * um jeito que não avisa: não quebra, encolhe.
 *
 * A medição é direta e não depende de ancestral nenhum:
 *
 *     altura = janela − topo da tabela − o que vem depois dela
 *
 * ## O que vem depois dela, que é o que faltava na fase 26
 *
 * A primeira versão media só o topo, e o rodapé (as notas de "como ler") ficava
 * fora da conta: a tabela ia até o fim da janela, o rodapé transbordava e a
 * **página** ganhava uma barra de rolagem própria. Duas barras, e a de fora
 * movia o cabeçalho que a de dentro acabara de prender.
 *
 * Somando os irmãos seguintes, o conjunto inteiro cabe na janela e a página não
 * tem por que rolar. Nenhum número fixo: se a faixa de retorno crescer ou o
 * rodapé encolher, a conta acompanha no mesmo quadro.
 */
export function SheetScroll({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const medir = () => {
      // Abaixo de `md` a tabela não é presa: numa tela estreita, limitá-la
      // deixaria a janela de leitura menor que a própria linha, e a página
      // rolar inteira é o comportamento certo.
      if (window.innerWidth < 768) {
        el.style.removeProperty("height");
        return;
      }

      const topo = el.getBoundingClientRect().top;

      // Os irmãos que vêm **depois** da tabela: rodapé, notas, o que houver.
      let depois = 0;
      for (let irmao = el.nextElementSibling; irmao; irmao = irmao.nextElementSibling) {
        depois += irmao.getBoundingClientRect().height;
      }

      const disponivel = Math.floor(window.innerHeight - topo - depois);
      // Um piso evita o caso degenerado em que o conteúdo acima já ocupa a
      // janela inteira e a tabela viraria uma fresta — aí é melhor deixá-la
      // usável e a página rolar um pouco.
      el.style.height = `${Math.max(disponivel, 220)}px`;
    };

    medir();
    // `ResizeObserver` no `body` pega o que muda **acima e abaixo** da tabela:
    // o painel de preferências abrindo, a faixa de retorno ganhando uma linha,
    // o aviso da taxa da estação sumindo quando ela é preenchida.
    const observador = new ResizeObserver(medir);
    observador.observe(document.body);
    window.addEventListener("resize", medir);
    return () => {
      observador.disconnect();
      window.removeEventListener("resize", medir);
    };
  }, []);

  return (
    <div ref={ref} className="sheet-scroll">
      {children}
    </div>
  );
}
