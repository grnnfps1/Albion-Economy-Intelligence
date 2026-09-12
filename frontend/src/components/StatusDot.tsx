import { statusLabel, statusTone } from "@/lib/format";

const TONE_CLASS: Record<string, string> = {
  ok: "bg-up",
  degraded: "bg-warn",
  down: "bg-down",
  unknown: "bg-line-strong",
};

export function StatusDot({ status }: { status: string | null | undefined }) {
  const tone = statusTone(status);
  return (
    <span className="inline-flex items-center gap-2">
      <span
        aria-hidden
        className={`inline-block size-2 rounded-full ${TONE_CLASS[tone]}`}
      />
      <span className="text-sm">{statusLabel(status)}</span>
    </span>
  );
}
