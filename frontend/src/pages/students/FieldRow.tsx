export function FieldRow({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-wide text-stone-400">{label}</p>
      <p className={strong ? "text-sm font-semibold text-brand-700" : "text-sm text-ink"}>{value}</p>
    </div>
  );
}
