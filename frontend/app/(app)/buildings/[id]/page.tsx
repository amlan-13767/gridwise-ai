"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { Badge, Card, Kpi, Note, PageHeader, Q, Table, Td, Empty } from "@/components/ui";
import { BandChart, Bars } from "@/components/charts";
import { inr, ist, istHour, n0, n1, n2, ZONE_COLOR } from "@/lib/format";
import { Gauge, Snowflake, Zap, Building2 } from "lucide-react";

export default function BuildingPage() {
  const { id } = useParams<{ id: string }>();
  const q = useQuery({ queryKey: ["bsum", id], queryFn: () => api(`/api/energy/building/${id}/summary?days=14`) });
  return (
    <Q q={q} h={500}>{(d: any) => {
      const b = d.building; const k = d.kpis;
      const fc = d.forecast.map((f: any) => ({ t: istHour(f.ts), kw: f.kw, band: [f.lower, f.upper] }));
      return (<>
        <PageHeader title={b.name} desc={`${b.zone} zone · ${b.type.replaceAll("_", " ")} · code ${b.code}`} right={<Link href={`/${b.zone.toLowerCase()}`} className="text-sm text-primary">← {b.zone} dashboard</Link>} />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Kpi label="Energy (14 days)" value={`${n0(k.total_kwh)} kWh`} icon={<Zap className="h-4 w-4" />} sub={`avg ${n0(k.avg_daily_kwh)} kWh/day`} />
          <Kpi label="Peak demand" value={`${n0(k.peak_kw)} kW`} icon={<Gauge className="h-4 w-4" />} tone="warn" />
          <Kpi label="Energy intensity" value={`${n1(k.kwh_per_m2)} kWh/m²`} icon={<Building2 className="h-4 w-4" />} sub={`${n0(b.floor_area)} m² floor area`} />
          <Kpi label="HVAC share" value={`${n1(k.hvac_pct)}%`} icon={<Snowflake className="h-4 w-4" />} tone="good" sub={`cost ${inr(k.cost)}`} />
        </div>
        <div className="mt-6 grid gap-4 xl:grid-cols-2">
          <Card title="Daily consumption"><Bars data={d.daily} x="bucket" series={[{ key: "kwh", label: "Energy", color: ZONE_COLOR[b.zone] }]} /></Card>
          <Card title="Last 7 days, hourly" subtitle="kWh per hour"><Bars data={d.hourly.slice(-72)} x="bucket" series={[{ key: "kwh", label: "Energy", color: ZONE_COLOR[b.zone] }]} /></Card>
        </div>
        <div className="mt-6 grid gap-4 xl:grid-cols-3">
          <Card className="xl:col-span-2" title="Predicted demand: next 24 hours" subtitle={d.forecast[0] ? `Model ${d.forecast[0].model} · 80% interval` : ""}>
            {fc.length ? <BandChart data={fc.map((r: any) => ({ t: r.t, kw: r.kw, band: r.band }))} x="t" /> : <Empty text="No forecast" />}
          </Card>
          <Card title="Sub-areas">{d.areas.length ? <ul className="space-y-2 text-sm">{d.areas.map((a: any) => <li key={a.name} className="flex justify-between"><span>{a.name}</span><Badge kind="normal">{a.type}</Badge></li>)}</ul> : <Empty text="No sub-areas configured" />}</Card>
        </div>
        <div className="mt-6 grid gap-4 xl:grid-cols-2">
          <Card title="Recent anomalies">{d.anomalies.length ? <Table head={["Time (IST)", "Severity", "Deviation", "Status"]}>{d.anomalies.map((a: any) => <tr key={a.id}><Td>{ist(a.timestamp)}</Td><Td><Badge kind={a.severity}>{a.severity}</Badge></Td><Td>+{n0(a.deviation)}%</Td><Td><Badge kind={a.status}>{a.status}</Badge></Td></tr>)}</Table> : <Empty text="No anomalies" />}</Card>
          <Card title="Recommendations">{d.recommendations.length ? <ul className="space-y-2 text-sm">{d.recommendations.map((r: any) => <li key={r.id} className="flex items-start justify-between gap-2"><span>{r.title}</span><Badge kind={r.status}>{r.status}</Badge></li>)}</ul> : <Empty text="None for this building" />}</Card>
        </div>
        {b.approximate && <div className="mt-4"><Note>Map position is an approximate demo location, not a surveyed coordinate. All data on this page is simulated.</Note></div>}
      </>);
    }}</Q>
  );
}
