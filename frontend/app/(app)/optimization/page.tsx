"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Play } from "lucide-react";
import { api, canManage, getUser } from "@/lib/api";
import { Badge, Btn, Card, Kpi, Note, PageHeader, Q, Table, Td } from "@/components/ui";
import { LineSeries } from "@/components/charts";
import { hh, inr, ist, n0, n1 } from "@/lib/format";

export default function Optimization() {
  const user = getUser(); const qc = useQueryClient();
  const [pp, setPp] = useState("2"); const [wl, setWl] = useState("0.5"); const [cap, setCap] = useState(""); const [sel, setSel] = useState<number | null>(null);
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api("/api/optimization/runs") });
  const id = sel ?? runs.data?.items?.[0]?.id;
  const det = useQuery({ queryKey: ["run", id], queryFn: () => api("/api/optimization/" + id), enabled: !!id });
  const run = useMutation({ mutationFn: () => api("/api/optimization/run", { method: "POST", body: { peak_penalty: Number(pp), waste_lambda: Number(wl), peak_cap_kw: cap ? Number(cap) : null } }),
    onSuccess: (r: any) => { r.status === "infeasible" ? toast.warning("No feasible schedule for these constraints") : toast.success("Optimisation complete"); setSel(r.id); qc.invalidateQueries({ queryKey: ["runs"] }); qc.invalidateQueries({ queryKey: ["run"] }); }, onError: (e: any) => toast.error(e.message) });
  const approve = useMutation({ mutationFn: () => api(`/api/optimization/${id}/approve`, { method: "POST" }), onSuccess: () => { toast.success("Approved as a recommendation (no equipment is controlled)"); qc.invalidateQueries({ queryKey: ["run"] }); qc.invalidateQueries({ queryKey: ["runs"] }); }, onError: (e: any) => toast.error(e.message) });
  return (
    <>
      <PageHeader title="Optimization Engine" desc="OR-Tools linear programme that shifts only flexible loads (water pumps, approved non-critical equipment) within permitted windows to cut tariff cost and peak demand. Essential loads are never moved. Simulation / recommendation mode only." />
      {canManage(user) && <Card title="Run scenario" subtitle="min Σ (tariff·grid + λ·waste) + μ·peak, subject to energy, capacity and window constraints">
        <div className="flex flex-wrap items-end gap-4">
          {[["Peak penalty μ (₹/kW)", pp, setPp], ["Waste weight λ", wl, setWl], ["Peak cap kW (optional)", cap, setCap]].map(([l, v, s]: any) => (
            <label key={l} className="flex flex-col gap-1 text-xs text-ink2">{l}<input value={v} onChange={(e) => s(e.target.value)} inputMode="decimal" className="w-40 rounded-lg border border-line px-2.5 py-1.5 text-sm text-ink" aria-label={l} /></label>))}
          <Btn onClick={() => run.mutate()} disabled={run.isPending} data-testid="run-opt"><Play className="h-4 w-4" />{run.isPending ? "Solving…" : "Run optimisation"}</Btn>
        </div></Card>}
      <Q q={det} h={400}>{(d: any) => { const r = d.result; return (
        <div className="mt-6 space-y-4">
          <div className="flex items-center gap-2 text-sm"><b>Run #{d.id}</b><Badge kind={d.status}>{d.status}</Badge><span className="text-muted">mode: {d.mode} · {ist(d.created_at)} IST</span>
            {canManage(user) && d.status === "pending_review" && <Btn variant="good" className="ml-auto" onClick={() => approve.mutate()}>Approve recommendation</Btn>}</div>
          {r.status !== "optimal" ? <Note tone="warn">{r.message}</Note> : <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Kpi label="Forecast peak" value={`${n0(r.forecast_peak.kw)} kW`} sub={`at ${hh(r.forecast_peak.local_hour)} IST`} tone="warn" />
              <Kpi label="Optimised peak" value={`${n0(r.optimized.peak_kw)} kW`} sub={`${n1(r.peak_reduction_kw)} kW lower`} tone="good" />
              <Kpi label="Baseline cost / day" value={inr(r.baseline.cost)} />
              <Kpi label="Estimated cost difference" value={inr(r.cost_difference)} sub="ESTIMATE, not achieved" tone="good" />
            </div>
            <Card title="Baseline vs optimised grid demand" subtitle="Forecast campus demand less simulated solar, by local hour">
              <LineSeries data={r.hours_local.map((h: number) => ({ h: hh(h), baseline: r.baseline.grid_kw[h], optimised: r.optimized.grid_kw[h], solar: r.solar_kw[h] }))} x="h"
                series={[{ key: "baseline", label: "Baseline grid", color: "#eb6834" }, { key: "optimised", label: "Optimised grid", color: "#2a78d6" }, { key: "solar", label: "Simulated solar", color: "#eda100" }]} />
            </Card>
            <div className="grid gap-4 xl:grid-cols-2">
              {r.shifts.map((s: any) => (<Card key={s.load} title={s.load} subtitle={`${n0(s.energy_kwh)} kWh/day · moved ${n1(s.moved_kwh)} kWh`}>
                <LineSeries data={r.hours_local.map((h: number) => ({ h: hh(h), baseline: s.baseline_kw[h], optimised: s.optimized_kw[h] }))} x="h" series={[{ key: "baseline", label: "Baseline", color: "#eb6834" }, { key: "optimised", label: "Optimised", color: "#2a78d6" }]} height={200} />
                <p className="mt-2 text-xs text-ink2"><b>Why:</b> {s.reason}</p></Card>))}
            </div>
            <Note>{r.essential_load_note} {r.data_note}</Note></>}
        </div>); }}</Q>
      <Card className="mt-6" title="Run history"><Q q={runs}>{(d: any) => <Table head={["Run", "Created (IST)", "Status", "Cost diff", "Peak change kW", ""]}>{d.items.map((x: any) => <tr key={x.id} className={x.id === id ? "bg-blue-50" : ""}><Td>#{x.id}</Td><Td>{ist(x.created_at)}</Td><Td><Badge kind={x.status}>{x.status}</Badge></Td><Td>{x.summary.cost_difference == null ? "-" : inr(x.summary.cost_difference)}</Td><Td>{x.summary.peak_reduction_kw == null ? "-" : n1(x.summary.peak_reduction_kw)}</Td><Td><Btn variant="ghost" onClick={() => setSel(x.id)}>View</Btn></Td></tr>)}</Table>}</Q></Card>
    </>
  );
}
