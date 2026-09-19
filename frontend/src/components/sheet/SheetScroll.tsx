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
 *
 * ## O que observar, que é onde isto já errou
 *
 * Observar o `body` **não** funciona: ele tem `min-h-dvh`, e quando o conteúdo
 * encolhe para menos de uma janela o `min-height` segura a altura. Medir só
 * reagia a crescer. Ver o comentário no `useEffect`.
 */

/**
 * Arredonda a altura para baixo, até caber um número inteiro de linhas.
 *
 * Sem isto a última linha aparece partida ao meio, e linha pela metade lê-se
 * como dado incompleto: o olho não sabe se o número está cortado ou se o valor
 * é aquele. Sobra menos de uma linha de folga, que é o preço.
 *
 * Mede a linha em vez de assumir: a altura muda com a densidade da tela (o
 * calculador usa ícone de 30px, os rankings usam 20px) e com o conteúdo — uma
 * linha com duas linhas de texto na célula de material é mais alta.
 */
function emLinhasInteiras(el: HTMLElement, disponivel: number): number {
  const cabecalho = el.querySelector("thead")?.getBoundingClientRect().height ?? 0;
  const primeira = el.querySelector("tbody tr")?.getBoundingClientRect().height ?? 0;
  if (primeira <= 0) return disponivel;

  // A barra de rolagem **horizontal** come altura por dentro do contêiner. Sem
  // descontá-la, a conta fecha em linhas inteiras e a última fica escondida
  // atrás da barra — o mesmo sintoma que esta função existe para eliminar.
  // `offsetHeight - clientHeight` é a medida real, e não um 15px chutado que
  // erra em cada sistema.
  const barra = Math.max(0, el.offsetHeight - el.clientHeight);

  const corpo = disponivel - cabecalho - barra;
  if (corpo <= primeira) return disponivel;
  return Math.floor(cabecalho + barra + Math.floor(corpo / primeira) * primeira);
}

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
      el.style.height = `${Math.max(emLinhasInteiras(el, disponivel), 220)}px`;
    };

    medir();

    // Observa o **pai**, não o `body`.
    //
    // O `body` tem `min-h-dvh`, e essa única classe quebrava metade da
    // medição. Abrir o rodapé empurra o conteúdo além da janela, o `body`
    // cresce e o observador dispara — funcionava. Fechar devolve o conteúdo
    // para **menos** que uma janela, e aí o `min-height` segura o `body`
    // exatamente em `100dvh`: a altura não muda, o `ResizeObserver` não tem o
    // que notificar, e a tabela fica presa no tamanho pequeno com um vão
    // embaixo.
    //
    // Era assimétrico de um jeito que confunde: o mecanismo parecia funcionar
    // porque o caso que se testa primeiro é o de abrir.
    //
    // O pai (`PageShell`) tem altura de conteúdo, sem piso, então encolhe
    // junto e notifica nas duas direções.
    const observador = new ResizeObserver(medir);
    if (el.parentElement) {
      observador.observe(el.parentElement);
    }

    // `ResizeObserver` só vê mudança de **tamanho**. O rodapé recolhível
    // remove o nó da árvore (`{aberto && children}`), e um irmão que deixa de
    // existir não emite evento de tamanho — o pai emite, mas só se a altura
    // dele de fato mudar. O `MutationObserver` cobre o caso de o conteúdo
    // trocar sem o pai mudar de tamanho.
    const mutacoes = new MutationObserver(medir);
    if (el.parentElement) {
      mutacoes.observe(el.parentElement, { childList: true, subtree: true });
    }

    window.addEventListener("resize", medir);
    return () => {
      observador.disconnect();
      mutacoes.disconnect();
      window.removeEventListener("resize", medir);
    };
  }, []);

  return (
    <div ref={ref} className="sheet-scroll">
      {children}
    </div>
  );
}
