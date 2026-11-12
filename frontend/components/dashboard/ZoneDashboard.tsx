"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, Kpi, Note, PageHeader, Q, Select, Table, Td, Empty } from "@/components/ui";
import { Bars, LineSeries, StackedArea, pivot } from "@/components/charts";
import { compact, hh, inr, n0, n1, ZONE_COLOR } from "@/lib/format";
import { Building2, Gauge, Moon, Snowflake, Sunset, Zap } from "lucide-react";

const TITLES: Record<string, string> = {
  Academic: "Academic energy: departments, laboratories, library and administration. Occupancy here is schedule-based, not observed.",
  Hostel: "Hostel energy: normalised per estimated occupied bed. Patterns are investigation leads - never conclusions about students.",
  Residential: "Residential energy: aggregate cluster-level data only. Household-level data is not collected or shown.",
};

export default function ZoneDashboard({ zone }: { zone: "Academic" | "Hostel" | "Residential" }) {
  const [days, setDays] = useState("30");
  const q = useQuery({ queryKey: ["zdash", zone, days], queryFn: () => api(`/api/energy/zone-dashboard/${zone.toLowerCase()}?days=${days}`) });
  return (
    <>
      <PageHeader title={`${zone} Area Energy`} desc={TITLES[zone]}
        right={<Select label="Period" value={days} onChange={setDays} options={[{ value: "7", label: "Last 7 days" }, { value: "30", label: "Last 30 days" }, { value: "90", label: "Last 90 days" }]} />} />
      <Q q={q} h={400}>{(d: any) => {
        if (d.restricted) return <><Note tone="warn">{d.note}</Note><Card className="mt-4" title="Aggregate daily consumption"><Bars data={d.daily} x="bucket" series={[{ key: "kwh", label: "Residential", color: ZONE_COLOR.Residential }]} /></Card></>;
        if (!d.buildings) return <Empty text="No data" />;
        const b = d.buildings; const tot = d.total_kwh;
        const night = b.reduce((s: number, x: any) => s + x.overnight_kwh_per_night, 0);
        const evening = b.reduce((s: number, x: any) => s + x.evening_peak_kw, 0);
        const p = pivot(d.by_building, "building");
        const top = [...b].slice(0, 6).map((x: any) => x.building);
        const stackData = p.data.map((r: any) => { const o: any = { bucket: r.bucket }; let other = 0; p.keys.forEach((k) => { if (top.includes(k)) o[k] = r[k]; else other += r[k] || 0; }); o["All others"] = other; return o; });
        return (<>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi label="Total consumption" value={`${compact(tot)} kWh`} icon={<Zap className="h-4 w-4" />} sub={`${d.days} days`} />
            <Kpi label="Estimated cost" value={inr(b.reduce((s: number, x: any) => s + x.cost, 0))} icon={<Gauge className="h-4 w-4" />} />
            <Kpi label={zone === "Academic" ? "Outside 08-18h (incl. weekends)" : "Overnight (00-05h) per night"} value={zone === "Academic" ? `${n1(d.outside_hours_kwh / tot * 100)}%` : `${n0(night)} kWh`} icon={<Moon className="h-4 w-4" />} sub={zone === "Academic" ? "share of total kWh" : "zone total"} />
            <Kpi label="HVAC share" value={`${n1(d.hvac_kwh / tot * 100)}%`} icon={<Snowflake className="h-4 w-4" />} sub="metered cooling load" tone="good" />
          </div>
          {zone !== "Academic" && <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Kpi label="Evening peak (18-22h)" value={`${n0(evening)} kW`} icon={<Sunset className="h-4 w-4" />} sub="average, sum of buildings" tone="warn" />
            {zone === "Hostel" && <Kpi label="Avg per occupied bed / day" value={`${n1(b.reduce((s: number, x: any) => s + (x.kwh_per_occupied_bed_per_day || 0), 0) / b.length)} kWh`} icon={<Building2 className="h-4 w-4" />} sub="occupied beds are ESTIMATED" />}</div>}
          <div className="mt-6 grid gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2" title="Daily consumption" subtitle="Top buildings, rest grouped"><StackedArea data={stackData} x="bucket" series={[...top, "All others"].map((k) => ({ key: k, label: k }))} height={300} /></Card>
            <Card title="Average hourly profile" subtitle="Zone kW by local hour"><LineSeries data={d.hourly_profile.map((r: any) => ({ ...r, h: hh(r.lhour) }))} x="h" series={[{ key: "kw", label: zone, color: ZONE_COLOR[zone] }]} height={300} /></Card>
          </div>
          {zone === "Academic" && <Card className="mt-6" title="Consumption by building type" subtitle="Department / laboratory / library / classroom grouping at building level"><Bars data={d.by_type} x="building_type" series={[{ key: "kwh", label: "Energy", color: ZONE_COLOR.Academic }]} height={220} /></Card>}
          <Card className="mt-6" title="Buildings" subtitle="Normalised for comparison">
            <Table head={zone === "Hostel" ? ["Hostel", "kWh", "Cost", "Peak kW", "kWh/m²", "Capacity", "Occupied beds*", "kWh/bed/day*", "Overnight kWh/night", "Evening kW", "HVAC %"] : ["Building", "Type", "kWh", "Cost", "Peak kW", "kWh/m²", "Overnight kWh/night", "HVAC %"]}>
              {b.map((x: any) => (<tr key={x.building_id} className="hover:bg-slate-50">
                <Td><Link className="text-primary hover:underline" href={`/buildings/${x.building_id}`}>{x.building}</Link></Td>
                {zone !== "Hostel" && <Td>{x.building_type.replaceAll("_", " ")}</Td>}
                <Td>{n0(x.kwh)}</Td><Td>{inr(x.cost)}</Td><Td>{n0(x.peak_kw)}</Td><Td>{n1(x.kwh_per_m2)}</Td>
                {zone === "Hostel" && <><Td>{x.capacity}</Td><Td>{n0(x.occupied_beds_estimate)}</Td><Td>{n2(x.kwh_per_occupied_bed_per_day)}</Td></>}
                <Td>{n1(x.overnight_kwh_per_night)}</Td>{zone === "Hostel" && <Td>{n1(x.evening_peak_kw)}</Td>}<Td>{n1(x.hvac_pct)}</Td></tr>))}
            </Table>
            {zone === "Hostel" && <p className="mt-2 text-xs text-muted">* Occupied beds are estimated from night-time presence in the simulated data; they are not observed counts.</p>}
          </Card>
          <div className="mt-4 space-y-2">{[d.note, d.submetering, d.patterns_note, d.privacy, d.solar_note].filter(Boolean).map((t: string) => <Note key={t}>{t}</Note>)}</div>
        </>);
      }}</Q>
    </>
  );
}
const n2 = (v: number | null | undefined) => (v == null ? "-" : v.toFixed(2));
