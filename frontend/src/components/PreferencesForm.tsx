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
 * Um formulário só, para todas as telas.
 *
 * Antes cada tela pedia os mesmos sete campos. Isso era eu levando "não
 * inventar número" longe demais: a regra é não inventar **em silêncio**, não
 * deixar a tela vazia esperando o usuário preencher.
 */
export function PreferencesForm({ initial }: { initial: Preferences }) {
  const router = useRouter();
  const [prefs, setPrefs] = useState(initial);
  const [pending, startTransition] = useTransition();
  const [salvo, setSalvo] = useState(false);

  function atualizar(patch: Partial<Preferences>) {
    const proximo = { ...prefs, ...patch };
    // Premium é a única coisa que muda outro campo sozinha: o imposto é metade.
    if (patch.premium !== undefined) {
      proximo.salesTaxPct = patch.premium ? 0.04 : 0.08;
    }
    setPrefs(proximo);
    setSalvo(false);
  }

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
    "figure w-full rounded-[3px] border border-line bg-raised px-2 py-1.5 text-[12px] text-body";
  const rotulo = "text-[10px] text-dim uppercase tracking-[0.05em]";

  return (
    <div className="grid gap-3 border-line border-b bg-sunken p-4 sm:grid-cols-3 lg:grid-cols-6">
      <label className="flex flex-col gap-1">
        <span className={rotulo}>Servidor</span>
        <select className={campo} value={prefs.server}
          onChange={(e) => atualizar({ server: e.target.value })}>
          <option value="west">Americas</option>
          <option value="east">Asia</option>
          <option value="europe">Europe</option>
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className={rotulo}>Comprar em</span>
        <select className={campo} value={prefs.buyLocation}
          onChange={(e) => atualizar({ buyLocation: e.target.value })}>
          {CIDADES.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className={rotulo}>Vender em</span>
        <select className={campo} value={prefs.sellLocation}
          onChange={(e) => atualizar({ sellLocation: e.target.value })}>
          {CIDADES.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className={rotulo}>Conta</span>
        <select className={campo} value={prefs.premium ? "1" : "0"}
          onChange={(e) => atualizar({ premium: e.target.value === "1" })}>
          <option value="1">Premium</option>
          <option value="0">Sem premium</option>
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className={rotulo}>Setup fee</span>
        <input className={campo} value={(prefs.setupFeePct * 100).toFixed(2)}
          onChange={(e) => atualizar({ setupFeePct: (parseFloat(e.target.value) || 0) / 100 })} />
      </label>

      <label className="flex flex-col gap-1">
        <span className={rotulo}>Imposto de venda</span>
        <input className={campo} value={(prefs.salesTaxPct * 100).toFixed(2)}
          onChange={(e) => atualizar({ salesTaxPct: (parseFloat(e.target.value) || 0) / 100 })} />
      </label>

      <label className="flex flex-col gap-1">
        <span className={rotulo}>Focus ligado</span>
        <select className={campo} value={prefs.useFocus ? "1" : "0"}
          onChange={(e) => atualizar({ useFocus: e.target.value === "1" })}>
          <option value="0">não</option>
          <option value="1">sim</option>
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className={rotulo}>Bônus diário</span>
        <select className={campo} value={String(prefs.dailyProductionBonus)}
          onChange={(e) => atualizar({ dailyProductionBonus: parseFloat(e.target.value) })}>
          <option value="0">nenhum</option>
          <option value="0.1">10%</option>
          <option value="0.2">20%</option>
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className={rotulo}>Taxa da estação (prata / 100 nutrição)</span>
        <input className={campo} value={prefs.stationFeePer100Nutrition}
          onChange={(e) =>
            atualizar({ stationFeePer100Nutrition: parseFloat(e.target.value) || 0 })} />
        <span className="text-[11px] text-zinc-500">
          O número que aparece na tela da estação. A taxa de cada item sai dele e
          cresce com o tier.
        </span>
      </label>

      <label className="flex flex-col gap-1">
        <span className={rotulo}>Focus disponível</span>
        <input className={campo} value={prefs.focusBudget}
          onChange={(e) => atualizar({ focusBudget: parseFloat(e.target.value) || 0 })} />
      </label>

      <label className="flex flex-col gap-1">
        <span className={rotulo}>Quantidade</span>
        <input className={campo} value={prefs.quantity}
          onChange={(e) => atualizar({ quantity: parseFloat(e.target.value) || 1 })} />
      </label>

      {/* Risco de rota. Zero é o padrão e significa "não estou modelando
          perda" — o lucro ajustado sai igual ao bruto, à vista. */}
      <label className="flex flex-col gap-1">
        <span className={rotulo}>Perda % · zona azul</span>
        <input className={campo} value={(prefs.lossPctBlue * 100).toFixed(1)}
          onChange={(e) => atualizar({ lossPctBlue: (parseFloat(e.target.value) || 0) / 100 })} />
      </label>

      <label className="flex flex-col gap-1">
        <span className={rotulo}>Perda % · vermelha/preta</span>
        <input className={campo} value={(prefs.lossPctRedBlack * 100).toFixed(1)}
          onChange={(e) =>
            atualizar({ lossPctRedBlack: (parseFloat(e.target.value) || 0) / 100 })
          } />
      </label>

      {/* Especialização por família. Zero não é "não informado": é "não
          especializado", e o custo em Focus sai igual ao do dump. */}
      {FAMILIAS.map(([chave, nome]) => (
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
      <div className="col-span-full flex flex-col gap-1.5">
        <span className={rotulo}>Spec por item · craft de equipamento</span>
        {itens.length === 0 && (
          <span className="text-[11px] text-dim">
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
              className="rounded-[3px] border border-line px-2 py-1 text-[11px] text-dim hover:border-down hover:text-down"
            >
              remover
            </button>
          </span>
        ))}
        <span>
          <button
            type="button"
            onClick={adicionarItem}
            className="rounded-[3px] border border-line-strong bg-raised px-2.5 py-1 text-[11px] text-body hover:border-warn"
          >
            + item
          </button>
          <span className="ml-2 text-[10.5px] text-dim">
            O tier e o encantamento são ignorados: o nó do Destiny Board é da linha do item.
          </span>
        </span>
      </div>

      <div className="flex items-end">
        <button type="button" onClick={salvar} disabled={pending}
          className="w-full rounded-[3px] border border-line-strong bg-raised px-3 py-1.5 text-[12px] text-body hover:border-warn disabled:opacity-50">
          {pending ? "Aplicando…" : salvo ? "Salvo ✓" : "Salvar"}
        </button>
      </div>

      <p className="col-span-full m-0 text-[11px] text-muted leading-relaxed sm:col-span-3 lg:col-span-6">
        <b className="font-semibold text-warn">Valores padrão, não verificados no jogo.</b>{" "}
        São o que a comunidade reporta. O imposto muda com Premium; o retorno muda com Focus e
        especialização; a taxa da estação é definida pelo dono e varia por cidade. Ajuste uma
        vez — vale para todas as telas.
      </p>

      <p className="col-span-full m-0 text-[11px] text-muted leading-relaxed sm:col-span-3 lg:col-span-6">
        <b className="font-semibold text-body">Especialização corta o Focus, não o custo.</b>{" "}
        Cada 10.000 pontos de eficiência cortam o custo pela metade, e cada nível de spec vale
        250 pontos. Um refino T4 custa 54 de Focus sem spec e 3 com tudo maximizado — dezoito
        vezes mais refino no mesmo dia. <b className="font-semibold text-warn">Com zero, as
        telas calculam assumindo spec 0</b> e dizem isso na linha.
      </p>

      <p className="col-span-full m-0 text-[11px] text-muted leading-relaxed sm:col-span-3 lg:col-span-6">
        <b className="font-semibold text-body">Refino é por família; craft é por item.</b>{" "}
        Quem especializa couro especializa a linha inteira, então cinco campos bastam para o
        refino. Craft de equipamento não funciona assim — quem especializou Capuz de Mercenário
        não especializou Capuz de Caçador, porque são nós diferentes do Destiny Board. Informe
        só os itens que você de fato produz; o resto continua em zero.
      </p>

      <p className="col-span-full m-0 text-[11px] text-muted leading-relaxed sm:col-span-3 lg:col-span-6">
        <b className="font-semibold text-body">O retorno de material não é mais um campo.</b>{" "}
        Ele sai de uma matriz por cidade, atividade e Focus — refinar minério em Thetford rende
        36,7%, e em qualquer outra cidade rende 15,2%. As telas mostram por linha onde rende
        mais. Estes dois campos escolhem a coluna da matriz e somam o sorteio do dia.
      </p>

      <p className="col-span-full m-0 text-[11px] text-muted leading-relaxed sm:col-span-3 lg:col-span-6">
        <b className="font-semibold text-body">Perda de carga começa em zero</b>, e zero não é
        um chute: é dizer que você não está modelando perda, e nesse caso o lucro ajustado sai
        igual ao bruto. Rota entre cidades reais é zona azul; qualquer ponta em Caerleon ou no
        Black Market atravessa vermelha/preta. Informe o número que a sua própria experiência
        mostra — ninguém tem esse dado além de você.
      </p>
    </div>
  );
}
