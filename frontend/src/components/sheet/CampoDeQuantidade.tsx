"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

/**
 * Quantidade por digitação, no lugar das pílulas.
 *
 * As pílulas ofereciam 1, 10, 100, 500 e 1000 — cinco valores escolhidos por
 * nós para uma pergunta que é do usuário. Quem produz 320 não tinha como
 * dizê-lo, e dois jeitos de informar a mesma coisa é o que se está eliminando.
 *
 * ## O foco é o problema difícil aqui, e é por isso que há estado local
 *
 * O caminho óbvio — `router.push` a cada tecla — **não funciona**: cada push
 * recarrega o componente de servidor, o `input` é recriado e o foco se perde.
 * Na prática dá para digitar um caractere por vez, e "1000" vira "1".
 *
 * Por isso o campo guarda o próprio texto e é **não controlado pela URL**: o
 * que o usuário digita fica aqui, e a URL só é reescrita depois de uma pausa.
 * O `useTransition` mantém o campo utilizável durante o recálculo, em vez de
 * congelar.
 *
 * ## Vazio e zero viram 1
 *
 * Quantidade zero não é um recorte, é uma divisão por zero esperando
 * acontecer: margens viram `NaN` e a tela mostra "NaN" em vinte linhas. Vazio
 * é estado legítimo **enquanto se digita** — apagar para trocar o número —, e
 * por isso ele não força nada na hora: só a URL recebe 1.
 */
const ATRASO_MS = 400;

export function CampoDeQuantidade({
  valor,
  chave = "quantity",
  rotulo = "quantidade",
}: {
  /** O que o backend **de fato usou** — a tela não afirma valor que não é dela. */
  valor: number;
  chave?: string;
  rotulo?: string;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [texto, setTexto] = useState(String(valor));
  const [pendente, startTransition] = useTransition();
  const digitando = useRef(false);

  // Quando a resposta chega com outro valor — porque alguém trocou de filtro,
  // ou abriu um link — o campo acompanha. Mas **não** enquanto se digita: aí
  // ele sobrescreveria o que a pessoa está escrevendo.
  useEffect(() => {
    if (!digitando.current) setTexto(String(valor));
  }, [valor]);

  useEffect(() => {
    if (!digitando.current) return;
    const id = setTimeout(() => {
      digitando.current = false;
      const numero = Math.max(1, Math.floor(Number(texto.replace(/\D/g, "")) || 1));
      if (numero === valor) return;
      const next = new URLSearchParams(params.toString());
      next.set(chave, String(numero));
      startTransition(() => router.push(`?${next.toString()}`));
    }, ATRASO_MS);
    return () => clearTimeout(id);
  }, [texto, valor, chave, params, router]);

  return (
    <label className="flex items-center gap-1.5 rounded-sm border border-line bg-raised px-2 py-1">
      <span className="lbl">{rotulo}</span>
      <input
        value={texto}
        inputMode="numeric"
        aria-label={rotulo}
        onChange={(e) => {
          digitando.current = true;
          // Só dígitos: um "e" ou um "-" no meio viraria `NaN` mais adiante, e
          // `NaN` na tela é pior que um campo que recusa a tecla.
          setTexto(e.target.value.replace(/\D/g, ""));
        }}
        onBlur={() => {
          if (texto === "" || Number(texto) < 1) setTexto("1");
        }}
        className={`figure w-16 border-0 bg-transparent p-0 text-right text-note text-body focus:outline-none ${
          pendente ? "opacity-60" : ""
        }`}
      />
    </label>
  );
}
