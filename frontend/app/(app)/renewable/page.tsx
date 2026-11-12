"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Battery, Sun, Wind } from "lucide-react";
import { api, canManage, getUser } from "@/lib/api";
import { Btn, Card, Kpi, Note, PageHeader, Q, Table, Td, Badge } from "@/components/ui";
import { Bars, LineSeries } from "@/components/charts";
import { istDay, istHour, n0, n1 } from "@/lib/format";

export default function Renewable() {
  const user = getUser(); const qc = useQueryClient();
  const ov = useQuery({ queryKey: ["ren-ov"], queryFn: () => api("/api/renewable/overview?days=7") });
  const fc = useQuery({ queryKey: ["ren-fc"], queryFn: () => api("/api/renewable/forecast") });
  const run = useMutation({ mutationFn: () => api("/api/renewable/forecast/run", { method: "POST" }), onSuccess: () => { toast.success("Solar forecast refreshed"); qc.invalidateQueries({ queryKey: ["ren-fc"] }); }, onError: (e: any) => toast.error(e.message) });
  return (
    <>
      <PageHeader title="Renewable Energy" desc="All generation shown is SIMULATED. No wind turbine, battery or real solar asset is assumed to exist."
        right={canManage(user) ? <Btn variant="ghost" onClick={() => run.mutate()} disabled={run.isPending}>Refresh solar forecast</Btn> : undefined} />
      <Note tone="warn">Simulated solar generation - never to be read as actual campus production.</Note>
      <Q q={ov} h={110}>{(o: any) => <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Simulated capacity" value={`${n0(o.total_capacity_kw)} kWp`} icon={<Sun className="h-4 w-4" />} sub={`${o.assets.length} simulated assets`} />
        <Kpi label="Solar energy (7 d)" value={`${n0(o.solar_kwh)} kWh`} tone="good" />
        <Kpi label="Renewable contribution" value={`${n1(o.renewable_pct)}%`} tone="good" sub="of campus demand" />
        <Kpi label="Forecast MAE (48 h)" value={`${n1(o.forecast_mae_kw_48h)} kW`} sub={o.forecast_model} />
        <Kpi label="Wind" value={<span className="text-lg">Not installed</span>} icon={<Wind className="h-4 w-4" />} sub={o.wind.note} />
        <Kpi label="Battery" value={<span className="text-lg">Not available</span>} icon={<Battery className="h-4 w-4" />} sub={o.battery.note} />
      </div>}</Q>
      <div className="mt-6 grid gap-4 xl:grid-cols-2">
        <Card title="Actual vs forecast solar (last 48 h)" subtitle="Backtest on held-out recent hours using observed weather inputs">
          <Q q={ov}>{(o: any) => <LineSeries data={o.actual_vs_forecast.map((r: any) => ({ t: istHour(r.ts), actual: r.actual_kw, forecast: r.forecast_kw }))} x="t" series={[{ key: "actual", label: "Actual (simulated)", color: "#0b1730" }, { key: "forecast", label: "Forecast", color: "#eda100" }]} dash={["", "5 3"]} />}</Q>
        </Card>
        <Card title="Historical renewable contribution" subtitle="Daily share of campus demand (%)">
          <Q q={ov}>{(o: any) => <Bars data={o.daily.map((r: any) => ({ d: r.ldate.slice(5), pct: r.renewable_pct }))} x="d" unit="%" series={[{ key: "pct", label: "Renewable share", color: "#1baf7a" }]} />}</Q>
        </Card>
      </div>
      <Card className="mt-6" title="Expected generation: next 24 hours" subtitle="Forecast vs predicted campus demand; uncertainty = 80% interval">
        <Q q={fc}>{(f: any) => (<div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-4"><Kpi label="Expected solar" value={`${n0(f.expected_solar_kwh)} kWh`} tone="good" /><Kpi label="Renewable share" value={`${n1(f.renewable_share_pct)}%`} /><Kpi label="Expected surplus" value={`${n0(f.expected_surplus_kwh)} kWh`} sub="solar above demand" /><Kpi label="Expected deficit (grid)" value={`${n0(f.expected_deficit_kwh)} kWh`} /></div>
          <LineSeries data={f.items.map((r: any) => ({ t: istHour(r.ts), solar: r.solar_kw, lower: r.lower, upper: r.upper }))} x="t" series={[{ key: "solar", label: "Solar forecast", color: "#eda100" }, { key: "lower", label: "Lower bound", color: "#cbd5e1" }, { key: "upper", label: "Upper bound", color: "#cbd5e1" }]} />
          <div><p className="mb-2 text-sm font-medium">Load-shifting suggestions (from latest optimisation run)</p>
            {f.load_shifting.length ? <Table head={["Flexible load", "Moved (kWh)", "Reason"]}>{f.load_shifting.map((s: any) => <tr key={s.load}><Td>{s.load}</Td><Td>{n1(s.moved_kwh)}</Td><Td className="whitespace-normal text-xs text-ink2">{s.reason}</Td></tr>)}</Table> : <p className="text-sm text-muted">Run the optimisation engine to generate suggestions.</p>}</div>
        </div>)}</Q>
      </Card>
      <Card className="mt-6" title="Simulated assets"><Q q={ov}>{(o: any) => <Table head={["Building", "Type", "Capacity", "Status", "Data source"]}>{o.assets.map((a: any) => <tr key={a.id}><Td>{a.building}</Td><Td>{a.type}</Td><Td>{a.capacity_kw} kWp</Td><Td>{a.status}</Td><Td><Badge kind={a.data_source}>{a.data_source}</Badge></Td></tr>)}</Table>}</Q></Card>
    </>
  );
}
