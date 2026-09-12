"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

export function RefreshButton() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  return (
    <button
      type="button"
      onClick={() => startTransition(() => router.refresh())}
      disabled={pending}
      className="rounded-sm border border-line-strong px-3 py-1.5 text-sm text-muted hover:text-body disabled:opacity-50"
    >
      {pending ? "Verificando…" : "Verificar de novo"}
    </button>
  );
}
