"use client";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Snowflake } from "lucide-react";
import { api, canManage, getUser } from "@/lib/api";
import { Badge, Btn, Card, Kpi, Note, PageHeader, Q, Table, Td, Empty, Select } from "@/components/ui";
import { LineSeries } from "@/components/charts";
import { hh, inr, n0, n1 } from "@/lib/format";

export default function Cooling() {
  const user = getUser(); const [sel, setSel] = useState<number | null>(null); const [zone, setZone] = useState("Academic");
  const ov = useQuery({ queryKey: ["cool-ov"], queryFn: () => api("/api/cooling/overview?days=14") });
  const an = useQuery({ queryKey: ["cool-an", zone], queryFn: () => api("/api/cooling/analysis?days=14&zone=" + zone) });
  const opt = useMutation({ mutationFn: (id: number) => api("/api/cooling/optimize", { method: "POST", body: { building_id: id } }), onError: (e: any) => toast.error(e.message), onSuccess: () => toast.success("Optimisation complete (recommendation only)") });
  const run = (id: number) => { setSel(id); opt.mutate(id); };
  const r = opt.data;
  return (
    <>
      <PageHeader title="Cooling Intelligence" desc="HVAC consumption analysis, occupancy-aware schedule checks and a constrained optimiser. Recommendation only: GRIDWISE AI never changes HVAC settings."
        right={<Select label="Zone" value={zone} onChange={setZone} options={["Academic", "Hostel", "Residential"].map((z) => ({ value: z, label: z }))} />} />
      <Q q={ov} h={100}>{(o: any) => <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Cooling energy (14 d)" value={`${n0(o.cooling_kwh)} kWh`} icon={<Snowflake className="h-4 w-4" />} />
        <Kpi label="HVAC share of total" value={`${n1(o.hvac_share_pct)}%`} tone="good" />
        <Kpi label="Schedules to review" value={o.flagged} tone={o.flagged ? "warn" : "good"} sub="cooling outside occupied hours" />
        <Kpi label="Estimated opportunity" value={`${n0(o.est_saving_kwh)} kWh`} sub={`≈ ${inr(o.est_saving_cost)} · ESTIMATE`} tone="good" /></div>}</Q>
      <Card className="mt-6" title="Building cooling analysis" subtitle="After-hours = outside operating hours (or weekend) with occupancy below 5% of capacity">
        <Q q={an}>{(d: any) => d.items.length ? <Table head={["Building", "Cooling kWh", "HVAC %", "After-hours cooling kWh", "Comfort in range*", "Basis", "Flag", ""]}>
          {d.items.map((c: any) => (<tr key={c.building_id} className={sel === c.building_id ? "bg-blue-50" : ""}>
            <Td>{c.building}</Td><Td>{n0(c.cooling_kwh)}</Td><Td>{n1(c.hvac_share_pct)}</Td><Td>{n0(c.after_hours_cooling_kwh)}</Td>
            <Td>{c.comfort_in_range_pct == null ? "-" : n1(c.comfort_in_range_pct) + "%"}</Td><Td><Badge kind="pending">{c.occupancy_basis}</Badge></Td>
            <Td>{c.schedule_flag ? <Badge kind="high">review schedule</Badge> : <Badge kind="normal">ok</Badge>}</Td>
            <Td>{(canManage(user) || user?.role === "zone_manager") && <Btn variant="ghost" onClick={() => run(c.building_id)} data-testid="optimize-btn">Optimise</Btn>}</Td></tr>))}
        </Table> : <Empty text="No cooling data" />}</Q>
        <p className="mt-2 text-xs text-muted">* Share of occupied hours with indoor temperature between 22 and 26.5 °C (simulated sensor). Academic occupancy is schedule-based, not observed.</p>
      </Card>
      {sel && <Card className="mt-6" title={r ? `Optimised cooling schedule: ${r.building}` : "Optimising…"} subtitle={r?.basis}>
        {opt.isPending ? <p className="text-sm text-ink2">Solving…</p> : r && (r.status === "optimal" ? <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3"><Kpi label="Estimated saving / day" value={`${n0(r.energy_saving_kwh)} kWh`} tone="good" sub="ESTIMATE vs observed baseline" /><Kpi label="Estimated cost / day" value={inr(r.cost_saving)} tone="good" /><Kpi label="Mode" value={<span className="text-lg">Recommendation</span>} sub="approval required" /></div>
          <LineSeries data={r.baseline_kw.map((b: number, h: number) => ({ h: hh(h), baseline: b, optimised: r.optimized_kw[h], occupied: r.occupied[h] ? Math.max(...r.baseline_kw) : 0 }))} x="h"
            series={[{ key: "baseline", label: "Baseline cooling", color: "#eb6834" }, { key: "optimised", label: "Optimised cooling", color: "#2a78d6" }]} />
          <Note>{r.explanation} Hours shaded as occupied in the model: {r.occupied.map((o: boolean, h: number) => (o ? h : null)).filter((x: any) => x !== null).length}.</Note>
          <Note tone="warn">{r.kind}. {r.note}</Note>
        </div> : <Note tone="warn">{r.message}</Note>)}
      </Card>}
    </>
  );
}
