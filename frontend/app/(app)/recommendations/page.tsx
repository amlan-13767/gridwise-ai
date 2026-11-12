"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, Search, X } from "lucide-react";
import { api, canManage, getUser, qs } from "@/lib/api";
import { Badge, Btn, Card, Empty, Note, PageHeader, Q, Select } from "@/components/ui";
import { inr, n0 } from "@/lib/format";

const TYPE_LABEL: Record<string, string> = { ai_generated: "AI-generated", rule_based_alert: "Rule-based alert", verified_action: "Verified action", measured_saving: "Measured saving" };

export default function Recs() {
  const user = getUser(); const qc = useQueryClient();
  const [status, setStatus] = useState("all"); const [type, setType] = useState("all"); const [pri, setPri] = useState("all"); const [zone, setZone] = useState("all");
  const [form, setForm] = useState<{ id: number; date: string; kwh: string } | null>(null);
  const q = useQuery({ queryKey: ["recs", status, type, pri, zone], queryFn: () => api("/api/recommendations" + qs({ status, type, priority: pri, zone, limit: 100 })) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["recs"] });
  const decide = useMutation({ mutationFn: (a: { id: number; decision: string }) => api(`/api/recommendations/${a.id}/review`, { method: "POST", body: { decision: a.decision } }), onSuccess: () => { toast.success("Decision recorded"); refresh(); }, onError: (e: any) => toast.error(e.message) });
  const patch = useMutation({ mutationFn: (a: { id: number; body: any }) => api(`/api/recommendations/${a.id}`, { method: "PATCH", body: a.body }), onSuccess: () => { toast.success("Updated"); setForm(null); refresh(); }, onError: (e: any) => toast.error(e.message) });
  const gen = useMutation({ mutationFn: () => api("/api/recommendations/generate", { method: "POST" }), onSuccess: (r: any) => { toast.success(`${r.new} new recommendation(s)`); refresh(); }, onError: (e: any) => toast.error(e.message) });
  const mgr = canManage(user);
  const upd = (p: Partial<{ date: string; kwh: string }>) => setForm((f) => (f ? { ...f, ...p } : f));
  return (
    <>
      <PageHeader title="AI Recommendations" desc="Each item shows its origin (AI-generated, rule-based, verified or measured), evidence and confidence. Predicted savings are estimates - only 'Measured' items reflect recorded results."
        right={<>
          <Select label="Status" value={status} onChange={setStatus} options={[{ value: "all", label: "Any" }, ...["pending", "approved", "investigating", "implemented", "rejected"].map((v) => ({ value: v, label: v }))]} />
          <Select label="Origin" value={type} onChange={setType} options={[{ value: "all", label: "Any" }, ...Object.entries(TYPE_LABEL).map(([v, l]) => ({ value: v, label: l }))]} />
          <Select label="Priority" value={pri} onChange={setPri} options={[{ value: "all", label: "Any" }, ...["high", "medium", "low"].map((v) => ({ value: v, label: v }))]} />
          <Select label="Zone" value={zone} onChange={setZone} options={[{ value: "all", label: "Any" }, ...["Academic", "Hostel", "Residential"].map((v) => ({ value: v, label: v }))]} />
          {mgr && <Btn variant="ghost" onClick={() => gen.mutate()}>Regenerate</Btn>}
        </>} />
      <Q q={q} h={300}>{(d: any) => d.items.length ? <div className="space-y-3">{d.items.map((r: any) => (
        <Card key={r.id} className="!p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2"><Badge kind={r.priority}>{r.priority}</Badge><Badge kind={r.type}>{TYPE_LABEL[r.type]}</Badge><Badge kind={r.status}>{r.status}</Badge><span className="text-xs text-muted">{r.zone} · {r.building}</span></div>
              <h3 className="mt-2 font-semibold">{r.title}</h3><p className="mt-1 text-sm text-ink2">{r.description}</p>
              <p className="mt-2 text-sm"><b>Recommended action:</b> {r.recommended_action}</p>
              {r.evidence && <details className="mt-2 text-xs text-ink2"><summary className="cursor-pointer text-primary">Supporting evidence</summary><pre className="mt-1 overflow-x-auto rounded-lg bg-slate-50 p-2">{JSON.stringify(r.evidence, null, 2)}</pre></details>}
            </div>
            <dl className="grid grid-cols-3 gap-4 text-right text-sm sm:grid-cols-1 sm:gap-1">
              <div><dt className="text-[11px] text-ink2">{r.saving_label}</dt><dd className="font-semibold">{r.measured_saving_kwh != null ? n0(r.measured_saving_kwh) : n0(r.estimated_energy_saving_kwh)} kWh</dd></div>
              <div><dt className="text-[11px] text-ink2">Cost (est.)</dt><dd className="font-semibold">{inr(r.estimated_cost_saving)}</dd></div>
              <div><dt className="text-[11px] text-ink2">Confidence</dt><dd className="font-semibold capitalize">{r.confidence}</dd></div>
            </dl>
          </div>
          {r.implemented_at && <p className="mt-2 text-xs text-ink2">Implemented {r.implemented_at.slice(0, 10)}</p>}
          {(mgr || user?.role === "zone_manager") && <div className="mt-3 flex flex-wrap gap-2 border-t border-line pt-3">
            {mgr && r.status === "pending" && <><Btn variant="good" onClick={() => decide.mutate({ id: r.id, decision: "approve" })} data-testid="approve-rec"><Check className="h-4 w-4" />Approve</Btn><Btn variant="ghost" onClick={() => decide.mutate({ id: r.id, decision: "reject" })}><X className="h-4 w-4" />Reject</Btn></>}
            {r.status !== "implemented" && r.status !== "rejected" && <Btn variant="ghost" onClick={() => decide.mutate({ id: r.id, decision: "investigate" })}><Search className="h-4 w-4" />Mark for investigation</Btn>}
            {mgr && (r.status === "approved" || r.status === "implemented") && <Btn variant="ghost" onClick={() => setForm({ id: r.id, date: new Date().toISOString().slice(0, 10), kwh: String(r.measured_saving_kwh ?? "") })}>{r.status === "implemented" ? "Record measured result" : "Mark implemented"}</Btn>}
          </div>}
          {form && form.id === r.id && <div className="mt-3 flex flex-wrap items-end gap-3 rounded-xl bg-slate-50 p-3">
            {r.status !== "implemented" && <label className="text-xs text-ink2">Implementation date<input type="date" value={form.date} onChange={(e) => upd({ date: e.target.value })} className="mt-1 block rounded-lg border border-line px-2 py-1 text-sm" /></label>}
            {r.status === "implemented" && <label className="text-xs text-ink2">Measured saving (kWh)<input value={form.kwh} onChange={(e) => upd({ kwh: e.target.value })} inputMode="decimal" className="mt-1 block w-40 rounded-lg border border-line px-2 py-1 text-sm" /></label>}
            <Btn onClick={() => patch.mutate({ id: r.id, body: r.status === "implemented" ? { measured_saving_kwh: Number(form.kwh) } : { status: "implemented", implemented_at: form.date + "T00:00:00" } })}>Save</Btn>
            <Btn variant="ghost" onClick={() => setForm(null)}>Cancel</Btn></div>}
        </Card>))}</div> : <Empty text="No recommendations match the filters" />}</Q>
      <div className="mt-4"><Note>Rule-based alerts come from deterministic thresholds. AI-generated items come from the optimiser/ML modules. Nothing here is applied automatically.</Note></div>
    </>
  );
}
