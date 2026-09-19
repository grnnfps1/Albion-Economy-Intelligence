"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { COOKIE, type Preferences, type SpecItem } from "@/lib/preferences-shared";

/**
 * As cinco linhas de recurso do refino.
 *
 * Por família e não item a item: a planilha faz item a item, mas isso seriam
 * centenas de campos para uma decisão que quase ninguém toma por item.
 */
const FAMILIAS: [keyof Preferences, string][] = [
  ["specLeather", "Couro"],
  ["specCloth", "Tecido"],
  ["specPlanks", "Tábuas"],
  ["specMetalbar", "Barras"],
  ["specStoneblock", "Blocos"],
];

const CIDADES = [
  ["caerleon", "Caerleon"], ["bridgewatch", "Bridgewatch"], ["lymhurst", "Lymhurst"],
  ["fort-sterling", "Fort Sterling"], ["martlock", "Martlock"],
  ["thetford", "Thetford"], ["brecilien", "Brecilien"],
];

/**
 * Todos os parâmetros que o formulário sabe pedir.
 *
 * Existe para cada tela poder declarar **o que ela de fato usa**. Parâmetro que
 * aparece e não afeta nada é pior que parâmetro ausente: ele ensina o usuário a
 * ignorar o painel inteiro, e a partir daí o que importa também passa
 * despercebido. Risco de rota no calculador era o caso claro — refinar numa
 * cidade não envolve viagem, e o campo só ocupava espaço.
 */
export type CampoPref =
  | "servidor"
  | "comprarEm"
  | "venderEm"
  | "premium"
  | "setupFee"
  | "imposto"
  | "focusLigado"
  | "bonusDoDia"
  | "taxaDaEstacao"
  | "focusDisponivel"
  | "focusPorDia"
  | "quantidade"
  | "risco"
  | "specFamilia"
  | "specPorItem";

export const TODOS_OS_CAMPOS: CampoPref[] = [
  "servidor", "comprarEm", "venderEm", "premium", "setupFee", "imposto",
  "focusLigado", "bonusDoDia", "taxaDaEstacao", "focusDisponivel", "focusPorDia",
  "quantidade", "risco", "specFamilia", "specPorItem",
];

/**
 * Um formulário só, para todas as telas.
 *
 * Antes cada tela pedia os mesmos sete campos. Isso era eu levando "não
 * inventar número" longe demais: a regra é não inventar **em silêncio**, não
 * deixar a tela vazia esperando o usuário preencher.
 *
 * `campos` recorta o conjunto por tela. O padrão é mostrar tudo: uma tela que
 * ainda não declarou o que usa continua como estava, e o recorte é uma decisão
 * explícita de quem a conhece — não um efeito colateral de esquecimento.
 */
export function PreferencesForm({
  initial,
  campos = TODOS_OS_CAMPOS,
}: {
  initial: Preferences;
  campos?: CampoPref[];
}) {
  const router = useRouter();
  const [prefs, setPrefs] = useState(initial);
  const [pending, startTransition] = useTransition();
  const [salvo, setSalvo] = useState(false);

  function atualizar(patch: Partial<Preferences>) {
    const proximo = { ...prefs, ...patch };
    // Premium é a única coisa que muda outro campo sozinha. Os dois valores
    // têm procedência própria desde a fase 21 — 4% medido no jogo com
    // notificação, 8% confirmado pelo usuário —, e não um derivado do outro.
    if (patch.premium !== undefined) {
      proximo.salesTaxPct = patch.premium ? 0.04 : 0.08;
    }
    setPrefs(proximo);
    setSalvo(false);
  }

  const mostra = (c: CampoPref) => campos.includes(c);

  // Cookie antigo não tem `specItems`; `?? []` evita quebrar quem já salvou.
  const itens: SpecItem[] = prefs.specItems ?? [];

  function trocarItem(indice: number, patch: Partial<SpecItem>) {
    atualizar({
      specItems: itens.map((linha, i) => (i === indice ? { ...linha, ...patch } : linha)),
    });
  }

  function adicionarItem() {
    atualizar({ specItems: [...itens, { item: "", level: 0 }] });
  }

  function removerItem(indice: number) {
    atualizar({ specItems: itens.filter((_, i) => i !== indice) });
  }

  function salvar() {
    document.cookie = `${COOKIE}=${encodeURIComponent(JSON.stringify(prefs))};path=/;max-age=31536000;samesite=lax`;
    setSalvo(true);
    startTransition(() => router.refresh());
  }

  const campo =
    "figure w-full rounded-[3px] border border-line bg-raised px-2 py-1.5 text-note text-body";
  const rotulo = "text-aux text-dim uppercase tracking-[0.05em]";

  return (
    <div className="grid gap-3 border-line border-b bg-sunken p-4 sm:grid-cols-3 lg:grid-cols-6">
      {mostra("servidor") && (
  <label className="flex flex-col gap-1">
          <span className={rotulo}>Servidor</span>
          <select className={campo} value={prefs.server}
            onChange={(e) => atualizar({ server: e.target.value })}>
            <option value="west">Americas</option>
            <option value="east">Asia</option>
            <option value="europe">Europe</option>
          </select>
        </label>
      )}

      {mostra("comprarEm") && (
  <label className="flex flex-col gap-1">
          <span className={rotulo}>Comprar em</span>
          <select className={campo} value={prefs.buyLocation}
            onChange={(e) => atualizar({ buyLocation: e.target.value })}>
            {CIDADES.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
          </select>
        </label>
      )}

      {mostra("venderEm") && (
  <label className="flex flex-col gap-1">
          <span className={rotulo}>Vender em</span>
          <select className={campo} value={prefs.sellLocation}
            onChange={(e) => atualizar({ sellLocation: e.target.value })}>
            {CIDADES.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
          </select>
        </label>
      )}

      {mostra("premium") && (
  <label className="flex flex-col gap-1">
          <span className={rotulo}>Conta</span>
          <select className={campo} value={prefs.premium ? "1" : "0"}
            onChange={(e) => atualizar({ premium: e.target.value === "1" })}>
            <option value="1">Premium</option>
            <option value="0">Sem premium</option>
          </select>
        </label>
      )}

      {mostra("setupFee") && (
  <label className="flex flex-col gap-1">
          <span className={rotulo}>Setup fee</span>
          <input className={campo} value={(prefs.setupFeePct * 100).toFixed(2)}
            onChange={(e) => atualizar({ setupFeePct: (parseFloat(e.target.value) || 0) / 100 })} />
        </label>
      )}

      {mostra("imposto") && (
  <label className="flex flex-col gap-1">
          <span className={rotulo}>Imposto de venda</span>
          <input className={campo} value={(prefs.salesTaxPct * 100).toFixed(2)}
            onChange={(e) => atualizar({ salesTaxPct: (parseFloat(e.target.value) || 0) / 100 })} />
        </label>
      )}

      {mostra("focusLigado") && (
  <label className="flex flex-col gap-1">
          <span className={rotulo}>Focus ligado</span>
          <select className={campo} value={prefs.useFocus ? "1" : "0"}
            onChange={(e) => atualizar({ useFocus: e.target.value === "1" })}>
            <option value="0">não</option>
            <option value="1">sim</option>
          </select>
        </label>
      )}

      {mostra("bonusDoDia") && (
  <label className="flex flex-col gap-1">
          <span className={rotulo}>Bônus do dia (%)</span>
          {/* Era um select de 0/10/20%. Virou campo livre porque o bônus é
              sorteado e não vem de uma lista fixa: três opções inventadas dariam
              ares de constante do jogo a um número que só está na tela. */}
          <input className={campo}
            placeholder="0"
            value={prefs.dailyProductionBonus ? prefs.dailyProductionBonus * 100 : ""}
            onChange={(e) => {
              const texto = e.target.value.trim();
              const numero = parseFloat(texto.replace(",", "."));
              atualizar({
                dailyProductionBonus:
                  texto === "" || !Number.isFinite(numero)
                    ? 0
                    : Math.min(100, Math.max(0, numero)) / 100,
              });
            }} />
        </label>
      )}

      {mostra("taxaDaEstacao") && (
  <label className="flex flex-col gap-1">
          <span className={rotulo}>Taxa da estação (prata / 100 nutrição)</span>
          {/* Único campo que **não** vem pré-preenchido. Não há valor defensável
              para pôr aqui, e o número está escrito na tela da estação. */}
          <input className={campo}
            placeholder="não informado"
            value={prefs.stationFeePer100Nutrition ?? ""}
            onChange={(e) => {
              const texto = e.target.value.trim();
              const numero = parseFloat(texto.replace(",", "."));
              atualizar({
                stationFeePer100Nutrition:
                  texto === "" || !Number.isFinite(numero) ? null : Math.max(0, numero),
              });
            }} />
          {/* O texto longo saiu: o aviso âmbar no topo da tabela do
              calculador (`StationFeePrompt`) já explica por que o campo nasce
              vazio e o que fazer. Explicar a mesma coisa em dois lugares é a
              regra "nada duplicado"; fica só onde ler o número, que é a única
              informação que o aviso não repete. */}
          <span className="text-note text-zinc-500">Está na tela da estação, no jogo.</span>
        </label>
      )}

      {mostra("focusDisponivel") && (
  <label className="flex flex-col gap-1">
          <span className={rotulo}>Focus disponível</span>
          <input className={campo} value={prefs.focusBudget}
            onChange={(e) => atualizar({ focusBudget: parseFloat(e.target.value) || 0 })} />
          <span className="text-note text-zinc-500">
            O estoque que você tem agora — acumula até 30.000.
          </span>
        </label>
      )}

      {/* Taxa, não estoque: é o que limita quanto se produz num dia típico, e
          o que torna craft e refino comparáveis com a fazenda. */}
      {mostra("focusPorDia") && (
  <label className="flex flex-col gap-1">
          <span className={rotulo}>Focus por dia</span>
          <input className={campo} value={prefs.focusPerDay ?? 10000}
            onChange={(e) => atualizar({ focusPerDay: parseFloat(e.target.value) || 0 })} />
          <span className="text-note text-zinc-500">
            Quanto regenera por dia — 10.000 com Premium.
          </span>
        </label>
      )}

      {mostra("quantidade") && (
  <label className="flex flex-col gap-1">
          <span className={rotulo}>Quantidade</span>
          <input className={campo} value={prefs.quantity}
            onChange={(e) => atualizar({ quantity: parseFloat(e.target.value) || 1 })} />
        </label>
      )}

      {/* Risco de rota. Zero é o padrão e significa "não estou modelando
          perda" — o lucro ajustado sai igual ao bruto, à vista. */}
      {mostra("risco") && (
  <label className="flex flex-col gap-1">
          <span className={rotulo}>Perda % · zona azul</span>
          <input className={campo} value={(prefs.lossPctBlue * 100).toFixed(1)}
            onChange={(e) => atualizar({ lossPctBlue: (parseFloat(e.target.value) || 0) / 100 })} />
        </label>
      )}

      {mostra("risco") && (
  <label className="flex flex-col gap-1">
          <span className={rotulo}>Perda % · vermelha/preta</span>
          <input className={campo} value={(prefs.lossPctRedBlack * 100).toFixed(1)}
            onChange={(e) =>
              atualizar({ lossPctRedBlack: (parseFloat(e.target.value) || 0) / 100 })
            } />
        </label>
      )}

      {/* Especialização por família. Zero não é "não informado": é "não
          especializado", e o custo em Focus sai igual ao do dump. */}
      {mostra("specFamilia") &&
        FAMILIAS.map(([chave, nome]) => (
        <label key={chave} className="flex flex-col gap-1">
          <span className={rotulo}>Spec · {nome}</span>
          <input className={campo} value={prefs[chave] as number}
            onChange={(e) =>
              atualizar({
                [chave]: Math.max(0, Math.min(100, parseFloat(e.target.value) || 0)),
              } as Partial<Preferences>)
            } />
          </label>
        ))}

      {/* Especialização por item, para craft de equipamento.

          Lista aberta em vez de campos fixos: a planilha de referência pede
          centenas de níveis, um por item do Destiny Board, e isso não cabe num
          formulário. Quem crafta duas peças informa duas. O resto fica em zero,
          com o aviso de sempre. */}
      {mostra("specPorItem") && (
      <div className="col-span-full flex flex-col gap-1.5">
        <span className={rotulo}>Spec por item</span>
        {itens.length === 0 && (
          <span className="text-note text-dim">
            Nenhum item informado — o craft de equipamento assume spec 0.
          </span>
        )}
        {itens.map((linha, i) => (
          <span key={i} className="flex flex-wrap items-center gap-1.5">
            <input
              className={`${campo} max-w-[22rem] flex-1`}
              placeholder="id do item, ex.: T5_HEAD_LEATHER_SET1"
              value={linha.item}
              onChange={(e) => trocarItem(i, { item: e.target.value })}
            />
            <input
              className={`${campo} w-20`}
              aria-label="nível de especialização"
              value={linha.level}
              onChange={(e) =>
                trocarItem(i, {
                  level: Math.max(0, Math.min(100, parseFloat(e.target.value) || 0)),
                })
              }
            />
            <button
              type="button"
              onClick={() => removerItem(i)}
              aria-label={`remover ${linha.item || "item"}`}
              className="rounded-[3px] border border-line px-2 py-1 text-note text-dim hover:border-down hover:text-down"
            >
              remover
            </button>
          </span>
        ))}
        <span>
          <button
            type="button"
            onClick={adicionarItem}
            className="rounded-[3px] border border-line-strong bg-raised px-2.5 py-1 text-note text-body hover:border-warn"
          >
            + item
          </button>
          <span className="ml-2 text-aux text-dim">
            O tier e o encantamento são ignorados: o nó do Destiny Board é da linha do item.
          </span>
        </span>
      </div>
      )}

      <div className="flex items-end">
        <button type="button" onClick={salvar} disabled={pending}
          className="w-full rounded-[3px] border border-line-strong bg-raised px-3 py-1.5 text-note text-body hover:border-warn disabled:opacity-50">
          {pending ? "Aplicando…" : salvo ? "Salvo ✓" : "Salvar"}
        </button>
      </div>

      <p className="col-span-full m-0 text-note text-muted leading-relaxed sm:col-span-3 lg:col-span-6">
        <b className="font-semibold text-up">Imposto e setup fee foram medidos no jogo.</b>{" "}
        4% com Premium saiu de uma notificação de venda do próprio jogo; 8% sem Premium foi
        confirmado à parte. O setup fee de 2,5% é cobrado na criação da ordem, nas duas pernas, e
        você paga mesmo que a ordem nunca execute. O retorno vem da fórmula e muda com cidade e
        Focus. Ajuste uma vez — vale para todas as telas.{" "}
        <b className="font-semibold text-body">A taxa da estação é a exceção:</b> ela nasce
        vazia, porque nenhum número seria honesto aqui e porque ela está escrita na tela da
        estação, dentro do jogo.
      </p>

      <p className="col-span-full m-0 text-note text-muted leading-relaxed sm:col-span-3 lg:col-span-6">
        <b className="font-semibold text-body">Especialização corta o Focus, não o custo.</b>{" "}
        Cada 10.000 pontos de eficiência cortam o custo pela metade, e cada nível de spec vale
        250 pontos. Um refino T4 custa 54 de Focus sem spec e 3 com tudo maximizado — dezoito
        vezes mais refino no mesmo dia. <b className="font-semibold text-warn">Com zero, as
        telas calculam assumindo spec 0</b> e dizem isso na linha.
      </p>

      <p className="col-span-full m-0 text-note text-muted leading-relaxed sm:col-span-3 lg:col-span-6">
        <b className="font-semibold text-body">Refino é por família; craft é por item.</b>{" "}
        Quem especializa couro especializa a linha inteira, então cinco campos bastam para o
        refino. Craft de equipamento não funciona assim — quem especializou Capuz de Mercenário
        não especializou Capuz de Caçador, porque são nós diferentes do Destiny Board. Informe
        só os itens que você de fato produz; o resto continua em zero.
      </p>

      <p className="col-span-full m-0 text-note text-muted leading-relaxed sm:col-span-3 lg:col-span-6">
        <b className="font-semibold text-body">O retorno de material não é mais um campo.</b>{" "}
        Ele sai de uma matriz por cidade, atividade e Focus — refinar minério em Thetford rende
        36,7%, e em qualquer outra cidade rende 15,2%. As telas mostram por linha onde rende
        mais. Estes dois campos escolhem a coluna da matriz e somam o sorteio do dia.
      </p>

      <p className="col-span-full m-0 text-note text-muted leading-relaxed sm:col-span-3 lg:col-span-6">
        <b className="font-semibold text-body">Perda de carga começa em zero</b>, e zero não é
        um chute: é dizer que você não está modelando perda, e nesse caso o lucro ajustado sai
        igual ao bruto. Rota entre cidades reais é zona azul; qualquer ponta em Caerleon ou no
        Black Market atravessa vermelha/preta. Informe o número que a sua própria experiência
        mostra — ninguém tem esse dado além de você.
      </p>
    </div>
  );
}
