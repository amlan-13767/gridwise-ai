"use client";
import { clsx } from "clsx";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import React from "react";

export const cx = clsx;

export function Card({ title, subtitle, right, children, className }: { title?: React.ReactNode; subtitle?: React.ReactNode; right?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={cx("min-w-0 rounded-2xl border border-line bg-surface p-5 shadow-[0_1px_2px_rgba(15,23,42,.04)] fade-in", className)}>
      {(title || right) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div><h3 className="text-[15px] font-semibold text-ink">{title}</h3>{subtitle && <p className="mt-0.5 text-xs text-ink2">{subtitle}</p>}</div>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

export function Kpi({ label, value, sub, icon, tone = "default" }: { label: string; value: React.ReactNode; sub?: React.ReactNode; icon?: React.ReactNode; tone?: "default" | "good" | "warn" | "bad" }) {
  const t = { default: "bg-blue-50 text-primary", good: "bg-emerald-50 text-good", warn: "bg-amber-50 text-warn", bad: "bg-red-50 text-bad" }[tone];
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-[0_1px_2px_rgba(15,23,42,.04)] fade-in" data-testid="kpi">
      <div className="flex items-center justify-between"><p className="text-xs font-medium text-ink2">{label}</p>{icon && <span className={cx("grid h-8 w-8 place-items-center rounded-lg", t)}>{icon}</span>}</div>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-ink">{value}</p>
      {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
    </div>
  );
}

const BADGE: Record<string, string> = {
  low: "bg-slate-100 text-slate-700", medium: "bg-amber-100 text-amber-800", high: "bg-orange-100 text-orange-800", critical: "bg-red-100 text-red-800",
  open: "bg-red-50 text-red-700", investigating: "bg-blue-50 text-blue-700", dismissed: "bg-slate-100 text-slate-600", resolved: "bg-emerald-50 text-emerald-700",
  pending: "bg-slate-100 text-slate-700", approved: "bg-emerald-50 text-emerald-700", rejected: "bg-slate-100 text-slate-500", implemented: "bg-emerald-100 text-emerald-800",
  simulated: "bg-violet-100 text-violet-800", real: "bg-emerald-100 text-emerald-800", online: "bg-emerald-50 text-emerald-700", stale: "bg-amber-100 text-amber-800",
  offline: "bg-red-50 text-red-700", never_seen: "bg-slate-100 text-slate-600", normal: "bg-emerald-50 text-emerald-700", elevated: "bg-amber-100 text-amber-800",
  anomaly: "bg-red-100 text-red-800", no_data: "bg-slate-100 text-slate-600", pending_review: "bg-amber-100 text-amber-800", production: "bg-emerald-100 text-emerald-800",
  infeasible: "bg-red-100 text-red-800", ai_generated: "bg-indigo-100 text-indigo-800", rule_based_alert: "bg-sky-100 text-sky-800",
  verified_action: "bg-teal-100 text-teal-800", measured_saving: "bg-emerald-100 text-emerald-800", archived: "bg-slate-100 text-slate-600",
};
export function Badge({ children, kind }: { children: React.ReactNode; kind?: string }) {
  const k = kind || String(children);
  return <span className={cx("inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium capitalize", BADGE[k] || "bg-slate-100 text-slate-700")}>{String(children).replaceAll("_", " ")}</span>;
}

export function Btn({ children, variant = "primary", className, ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" | "good" }) {
  const v = { primary: "bg-primary text-white hover:bg-blue-700", ghost: "border border-line bg-white text-ink hover:bg-slate-50", danger: "bg-bad text-white hover:bg-red-700", good: "bg-good text-white hover:bg-emerald-700" }[variant];
  return <button {...p} className={cx("inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50", v, className)}>{children}</button>;
}

export function Select({ label, value, onChange, options, className }: { label?: string; value: string | number; onChange: (v: string) => void; options: { value: string | number; label: string }[]; className?: string }) {
  return (
    <label className={cx("flex flex-col gap-1 text-xs text-ink2", className)}>
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="rounded-lg border border-line bg-white px-2.5 py-1.5 text-sm text-ink outline-none focus:border-primary" aria-label={label}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

export function Segmented({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-slate-50 p-0.5" role="tablist">
      {options.map((o) => (
        <button key={o.value} role="tab" aria-selected={value === o.value} onClick={() => onChange(o.value)}
          className={cx("rounded-md px-3 py-1 text-xs font-medium transition", value === o.value ? "bg-white text-primary shadow-sm" : "text-ink2 hover:text-ink")}>{o.label}</button>
      ))}
    </div>
  );
}

export function Loading({ h = 220 }: { h?: number }) {
  return <div className="skeleton w-full" style={{ height: h }} aria-busy="true" role="status" aria-label="Loading" />;
}
export function Spinner() { return <Loader2 className="h-4 w-4 animate-spin" />; }
export function ErrorBox({ error }: { error: unknown }) {
  return <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert"><AlertTriangle className="h-4 w-4" />{(error as Error)?.message || "Something went wrong"}</div>;
}
export function Empty({ text }: { text: string }) {
  return <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line py-10 text-sm text-muted"><Inbox className="h-6 w-6" />{text}</div>;
}
export function Note({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "warn" }) {
  return <p className={cx("rounded-lg px-3 py-2 text-xs", tone === "warn" ? "bg-amber-50 text-amber-900" : "bg-blue-50 text-blue-900")}>{children}</p>;
}
export function PageHeader({ title, desc, right }: { title: string; desc?: string; right?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>{desc && <p className="mt-1 max-w-3xl text-sm text-ink2">{desc}</p>}</div>
      {right && <div className="flex flex-wrap items-end gap-3">{right}</div>}
    </div>
  );
}
export function Q<T>({ q, h, children }: { q: { isLoading: boolean; error: unknown; data?: T }; h?: number; children: (d: T) => React.ReactNode }) {
  if (q.isLoading) return <Loading h={h} />;
  if (q.error) return <ErrorBox error={q.error} />;
  if (!q.data) return <Empty text="No data" />;
  return <>{children(q.data)}</>;
}
export function Table({ head, children }: { head: string[]; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead><tr className="border-b border-line text-xs text-ink2">{head.map((h) => <th key={h} className="whitespace-nowrap px-3 py-2 font-medium">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  );
}
export const Td = ({ children, className }: { children?: React.ReactNode; className?: string }) => <td className={cx("whitespace-nowrap px-3 py-2.5 text-ink", className)}>{children}</td>;
