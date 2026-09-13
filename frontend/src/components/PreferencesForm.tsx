"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { COOKIE, type Preferences } from "@/lib/preferences-shared";

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
        <span className={rotulo}>Retorno de material</span>
        <input className={campo} value={(prefs.returnRate * 100).toFixed(1)}
          onChange={(e) => atualizar({ returnRate: (parseFloat(e.target.value) || 0) / 100 })} />
      </label>

      <label className="flex flex-col gap-1">
        <span className={rotulo}>Taxa da estação</span>
        <input className={campo} value={prefs.stationFee}
          onChange={(e) => atualizar({ stationFee: parseFloat(e.target.value) || 0 })} />
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
    </div>
  );
}
