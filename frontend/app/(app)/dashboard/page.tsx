"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, DollarSign, Gauge, Leaf, PiggyBank, Sun, Zap } from "lucide-react";
import { api, qs } from "@/lib/api";
import { Badge, Card, Empty, Kpi, Loading, PageHeader, Q, Segmented, Select, Note } from "@/components/ui";
import { Bars, LineSeries, StackedArea, pivot } from "@/components/charts";
import { compact, hh, inr, ist, n0, n1, ZONE_COLOR } from "@/lib/format";

export default function Dashboard() {
  const [days, setDays] = useState("30"); const [zone, setZone] = useState("all"); const [bld, setBld] = useState("all");
  const [source, setSource] = useState("all"); const [gran, setGran] = useState("day");
  const f = { days, zone, building_id: bld, source };
  const blds = useQuery({ queryKey: ["blds-all"], queryFn: () => api("/api/buildings?limit=200") });
  const ov = useQuery({ queryKey: ["ov", f], queryFn: () => api("/api/energy/overview" + qs(f)) });
  const cons = useQuery({ queryKey: ["cons", f, gran], queryFn: () => api("/api/energy/consumption" + qs({ ...f, granularity: gran === "hour" ? "hour" : gran, group: "zone", days: gran === "hour" ? Math.min(Number(days), 3) : days })) });
  const zones = useQuery({ queryKey: ["zones", days], queryFn: () => api("/api/energy/zones?days=" + days) });
  const peak = useQuery({ queryKey: ["peak", days, zone], queryFn: () => api("/api/energy/peak-demand" + qs({ days, zone })) });
  const bl = useQuery({ queryKey: ["blist", days, zone], queryFn: () => api("/api/energy/buildings" + qs({ days, zone })) });
  const an = useQuery({ queryKey: ["an-top"], queryFn: () => api("/api/anomalies?status=open&days=7&limit=6") });
  const fc = useQuery({ queryKey: ["fc-campus"], queryFn: () => api("/api/forecast?scope=campus&horizon=24_hours").catch(() => null) });
  const bOpts = [{ value: "all", label: "All buildings" }, ...((blds.data?.items || []).filter((b: any) => zone === "all" || b.zone_type === zone).map((b: any) => ({ value: b.id, label: b.building_name })))];
  const o = ov.data;
  return (
    <>
      <PageHeader title="Campus Energy Command Centre" desc="Unified view of electricity demand, cost, renewables and anomalies across all zones."
        right={<>
          <Select label="Period" value={days} onChange={setDays} options={[{ value: "7", label: "Last 7 days" }, { value: "30", label: "Last 30 days" }, { value: "60", label: "Last 60 days" }, { value: "90", label: "Last 90 days" }]} />
          <Select label="Zone" value={zone} onChange={(v) => { setZone(v); setBld("all"); }} options={[{ value: "all", label: "All zones" }, { value: "Academic", label: "Academic" }, { value: "Hostel", label: "Hostel" }, { value: "Residential", label: "Residential" }]} />
          <Select label="Building" value={bld} onChange={setBld} options={bOpts} />
          <Select label="Energy source" value={source} onChange={setSource} options={[{ value: "all", label: "All sources" }, { value: "simulated", label: "Simulated" }, { value: "real", label: "Real meters" }]} />
        </>} />
      {ov.isLoading ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Loading key={i} h={96} />)}</div> : o?.empty ? <Empty text="No readings match these filters" /> :
        o && <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Kpi label="Total consumption" value={`${compact(o.total_kwh)} kWh`} sub={`last ${o.period.days} days`} icon={<Zap className="h-4 w-4" />} />
          <Kpi label="Current demand" value={`${n0(o.current_kw)} kW`} sub="latest hour" icon={<Gauge className="h-4 w-4" />} />
          <Kpi label="Estimated cost" value={inr(o.estimated_cost)} sub="tariff assumption applied" icon={<DollarSign className="h-4 w-4" />} />
          <Kpi label="Peak demand" value={`${n0(o.peak?.kw)} kW`} sub={o.peak ? ist(o.peak.timestamp) + " IST" : ""} icon={<Activity className="h-4 w-4" />} tone="warn" />
          <Kpi label="Renewable generation" value={`${compact(o.renewable_kwh)} kWh`} sub="SIMULATED solar" icon={<Sun className="h-4 w-4" />} tone="good" />
          <Kpi label="Renewable contribution" value={`${n1(o.renewable_pct)}%`} sub="of consumption (simulated)" icon={<Leaf className="h-4 w-4" />} tone="good" />
          <Kpi label="Saving opportunities" value={`${compact(o.saving_opportunity_kwh)} kWh`} sub="ESTIMATED, not achieved" icon={<PiggyBank className="h-4 w-4" />} tone="good" />
          <Kpi label="Active anomalies" value={o.active_anomalies} sub="open, last 7 days" icon={<AlertTriangle className="h-4 w-4" />} tone={o.active_anomalies ? "bad" : "good"} />
        </div>}
      <div className="mt-6 grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2" title="Electricity consumption" subtitle="Stacked by zone"
          right={<Segmented value={gran} onChange={setGran} options={[{ value: "hour", label: "Hourly" }, { value: "day", label: "Daily" }, { value: "week", label: "Weekly" }, { value: "month", label: "Monthly" }]} />}>
          <Q q={cons}>{(d: any) => { const p = pivot(d.items, "zone"); return p.data.length ? <StackedArea data={p.data} x="bucket" series={p.keys.map((k) => ({ key: k, label: k, color: ZONE_COLOR[k] }))} /> : <Empty text="No data" />; }}</Q>
        </Card>
        <Card title="Peak-demand pattern" subtitle="Average and maximum campus kW by local hour">
          <Q q={peak}>{(d: any) => <LineSeries data={d.hourly_pattern.map((r: any) => ({ ...r, h: hh(r.hour) }))} x="h" series={[{ key: "avg_kw", label: "Average", color: "#2a78d6" }, { key: "max_kw", label: "Maximum", color: "#eb6834" }]} />}</Q>
        </Card>
      </div>
      <h2 className="mb-3 mt-8 text-sm font-semibold text-ink2">Zone comparison (normalised metrics)</h2>
      <Q q={zones} h={180}>{(d: any) => <div className="grid gap-4 lg:grid-cols-3">{d.items.map((z: any) => (
        <Link href={`/${z.zone.toLowerCase()}`} key={z.zone} className="block"><Card className="transition hover:shadow-md">
          <div className="mb-3 flex items-center gap-2"><span className="h-3 w-3 rounded-full" style={{ background: ZONE_COLOR[z.zone] }} /><h3 className="font-semibold">{z.zone}</h3><span className="ml-auto text-xs text-muted">{z.buildings} buildings</span></div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <div><dt className="text-xs text-ink2">{z.zone === "Residential" ? "Aggregate consumption" : "Electricity"}</dt><dd className="font-semibold">{compact(z.kwh)} kWh</dd></div>
            <div><dt className="text-xs text-ink2">Peak demand</dt><dd className="font-semibold">{n0(z.peak_kw)} kW</dd></div>
            <div><dt className="text-xs text-ink2">Cost</dt><dd className="font-semibold">{inr(z.cost)}</dd></div>
            <div><dt className="text-xs text-ink2">{z.zone === "Hostel" ? "Per occupied bed / day" : z.zone === "Academic" ? "Energy intensity" : "Per floor area"}</dt>
              <dd className="font-semibold">{z.zone === "Hostel" ? `${n1(z.kwh_per_occupied_bed_per_day)} kWh` : `${n1(z.kwh_per_m2)} kWh/m²`}</dd></div>
            <div className="col-span-2"><dt className="text-xs text-ink2">Potential savings (estimate)</dt><dd className="font-semibold text-good">{n0(z.potential_saving_kwh)} kWh</dd></div>
          </dl></Card></Link>))}</div>}</Q>
      <div className="mt-6 grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2" title="Building comparison" subtitle="Total kWh in period (top 12)">
          <Q q={bl}>{(d: any) => <Bars layout="vertical" data={d.items.slice(0, 12)} x="building" series={[{ key: "kwh", label: "Energy", color: "#2a78d6" }]} height={360} />}</Q>
        </Card>
        <Card title="AI alerts" subtitle="Open anomalies (investigation leads)" right={<Link href="/anomalies" className="text-xs text-primary">View all</Link>}>
          <Q q={an}>{(d: any) => d.items.length ? <ul className="space-y-3">{d.items.map((a: any) => (
            <li key={a.id} className="rounded-xl border border-line p-3 text-sm">
              <div className="flex items-center justify-between"><b>{a.building}</b><Badge kind={a.severity}>{a.severity}</Badge></div>
              <p className="mt-1 text-xs text-ink2">{ist(a.timestamp)} IST · {n1(a.observed_kw)} kW vs {n1(a.expected_kw)} expected (+{n0(a.deviation_pct)}%)</p>
              <p className="mt-1 text-xs text-muted">Method: {a.detection_method.replaceAll("_", " ")} · {a.recommended_investigation}</p>
            </li>))}</ul> : <Empty text="No open anomalies" />}</Q>
          <Q q={fc}>{(d: any) => d && d.forecast?.length ? <Note tone="warn">Forecast next 24h: peak {n0(Math.max(...d.forecast.map((x: any) => x.kw)))} kW · model {d.model_version}. <Link className="underline" href="/forecast">Details</Link></Note> : null}</Q>
        </Card>
      </div>
    </>
  );
}
