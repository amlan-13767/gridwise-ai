"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { RefreshCw } from "lucide-react";
import { api, canManage, getUser, qs } from "@/lib/api";
import { Btn, Card, Kpi, Note, PageHeader, Q, Select, Table, Td, Badge } from "@/components/ui";
import { BandChart } from "@/components/charts";
import { ist, istHour, n0, n2 } from "@/lib/format";

export default function Forecast() {
  const user = getUser(); const qc = useQueryClient();
  const [scope, setScope] = useState("campus"); const [zone, setZone] = useState("Academic"); const [bld, setBld] = useState(""); const [hz, setHz] = useState("24_hours");
  const blds = useQuery({ queryKey: ["blds-all"], queryFn: () => api("/api/buildings?limit=200") });
  const building = bld || blds.data?.items?.[0]?.id;
  const f = useQuery({ queryKey: ["fc", scope, zone, building, hz], enabled: scope !== "building" || !!building,
    queryFn: () => api("/api/forecast" + qs({ scope, horizon: hz, zone: scope === "zone" ? zone : undefined, building_id: scope === "building" ? building : undefined })) });
  const ev = useQuery({ queryKey: ["fc-eval"], queryFn: () => api("/api/forecast/evaluation") });
  const run = useMutation({ mutationFn: () => api("/api/forecast/run", { method: "POST" }), onSuccess: () => { toast.success("Forecasts regenerated"); qc.invalidateQueries({ queryKey: ["fc"] }); }, onError: (e: any) => toast.error(e.message) });
  const hzOpts = [{ value: "1_hour", label: "Next hour" }, { value: "24_hours", label: "Next 24 hours" }, { value: "7_days", label: "Next 7 days" }];
  return (
    <>
      <PageHeader title="Energy Demand Forecasting" desc="Tree-based models trained on simulated history and compared against a historical hourly-average baseline. Future weather uses a recent-days climatology (no live weather feed)."
        right={<>
          <Select label="Scope" value={scope} onChange={setScope} options={[{ value: "campus", label: "Entire campus" }, { value: "zone", label: "Zone" }, { value: "building", label: "Building" }]} />
          {scope === "zone" && <Select label="Zone" value={zone} onChange={setZone} options={["Academic", "Hostel", "Residential"].map((z) => ({ value: z, label: z }))} />}
          {scope === "building" && <Select label="Building" value={building || ""} onChange={setBld} options={(blds.data?.items || []).map((b: any) => ({ value: b.id, label: b.building_name }))} />}
          <Select label="Horizon" value={hz} onChange={setHz} options={hzOpts} />
          {canManage(user) && <Btn onClick={() => run.mutate()} disabled={run.isPending} variant="ghost"><RefreshCw className={`h-4 w-4 ${run.isPending ? "animate-spin" : ""}`} />Re-run forecast</Btn>}
        </>} />
      <Q q={f} h={420}>{(d: any) => {
        const map = new Map<string, any>();
        d.actual.slice(hz === "7_days" ? -48 : -36).forEach((a: any) => map.set(a.ts, { t: hz === "7_days" ? ist(a.ts, { weekday: "short", hour: "2-digit", hour12: false }) : istHour(a.ts), actual: a.kw }));
        d.forecast.forEach((p: any) => map.set(p.ts, { ...(map.get(p.ts) || {}), t: hz === "7_days" ? ist(p.ts, { weekday: "short", hour: "2-digit", hour12: false }) : istHour(p.ts), kw: p.kw, band: [p.lower, p.upper] }));
        const rows = [...map.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([, v]) => v);
        const peak = d.forecast.reduce((m: any, x: any) => (x.kw > m.kw ? x : m), d.forecast[0] || { kw: 0 });
        return (<>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi label="Predicted energy" value={`${n0(d.predicted_kwh)} kWh`} sub={`range ${n0(d.lower_kwh)} - ${n0(d.upper_kwh)} kWh`} />
            <Kpi label="Forecast peak" value={`${n0(peak.kw)} kW`} sub={peak.ts ? ist(peak.ts) + " IST" : ""} tone="warn" />
            <Kpi label="Model version" value={<span className="text-lg">{d.model_version}</span>} sub={d.generated_at ? "generated " + ist(d.generated_at) : ""} />
            <Kpi label="Data" value={<span className="text-lg">Simulated</span>} sub="not real campus load" />
          </div>
          <Card className="mt-4" title="Actual vs predicted demand" subtitle={d.interval}><BandChart data={rows} x="t" height={340} /></Card>
        </>);
      }}</Q>
      <Card className="mt-6" title="Model evaluation (held-out chronological test set)" subtitle="Computed by the training pipeline on SIMULATED data. Lower is better.">
        <Q q={ev}>{(r: any) => (<div className="space-y-5">
          {Object.entries(r.horizons).map(([h, res]: any) => {
            const names = Object.keys(res).filter((k) => res[k]?.rmse !== undefined);
            return (<div key={h}>
              <p className="mb-1 text-sm font-medium">{h.replace("_", " ")} horizon · selected by validation RMSE: <b>{res.selected_by_validation_rmse}</b> · RMSE change vs baseline: <b className={res.improvement_vs_baseline_rmse_pct >= 0 ? "text-good" : "text-bad"}>{res.improvement_vs_baseline_rmse_pct.toFixed(1)}%</b></p>
              <Table head={["Model", "MAE (kW)", "RMSE (kW)", "MAPE %", "sMAPE %"]}>{names.map((m) => (
                <tr key={m} className={m === res.selected_by_validation_rmse ? "bg-blue-50/60" : ""}><Td>{m.replaceAll("_", " ")} {m === "baseline_hourly_average" && <Badge kind="pending">baseline</Badge>}</Td><Td>{n2(res[m].mae)}</Td><Td>{n2(res[m].rmse)}</Td><Td>{res[m].mape == null ? "-" : n2(res[m].mape)}</Td><Td>{n2(res[m].smape)}</Td></tr>))}</Table>
            </div>);
          })}
          <Note tone="warn">{r.note} Trained {ist(r.trained_at)} · split: {r.split.method}. A model can fail to beat the baseline at some horizons (see negative changes above); that is reported, not hidden.</Note>
        </div>)}</Q>
      </Card>
    </>
  );
}
