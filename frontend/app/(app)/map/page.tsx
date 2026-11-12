"use client";
import dynamic from "next/dynamic";
import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Badge, Card, Loading, Note, PageHeader, Q, Segmented, Empty } from "@/components/ui";
import { LineSeries } from "@/components/charts";
import { ist, istHour, n0, n1 } from "@/lib/format";

const CampusMap = dynamic(() => import("@/components/maps/CampusMap"), { ssr: false, loading: () => <Loading h={560} /> });
const LEGEND = [["#16a34a", "Normal"], ["#eab308", "Higher than expected"], ["#dc2626", "Active anomaly"], ["#94a3b8", "No data"]];

export default function MapPage() {
  const [zone, setZone] = useState("all"); const [sel, setSel] = useState<any>(null);
  const bl = useQuery({ queryKey: ["map-b"], queryFn: () => api("/api/energy/buildings?days=7") });
  const ren = useQuery({ queryKey: ["map-r"], queryFn: () => api("/api/renewable/overview?days=1") });
  const det = useQuery({ queryKey: ["map-d", sel?.building_id], queryFn: () => api(`/api/energy/building/${sel.building_id}/summary?days=7`), enabled: !!sel });
  return (
    <>
      <PageHeader title="Campus Energy Map" desc="Building status from the latest hour versus a comparable-hours baseline. Click a building for details."
        right={<Segmented value={zone} onChange={setZone} options={[{ value: "all", label: "All" }, { value: "Academic", label: "Academic" }, { value: "Hostel", label: "Hostel" }, { value: "Residential", label: "Residential" }]} />} />
      <Note tone="warn">Positions are approximate DEMO locations and meter locations are SIMULATED - they do not indicate real installed hardware or actual NIT Rourkela building coordinates.</Note>
      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2 !p-3">
          <Q q={bl} h={560}>{(d: any) => <CampusMap buildings={d.items.filter((b: any) => zone === "all" || b.zone === zone)} solar={(ren.data?.assets || []).map((a: any) => a.building)} selected={sel?.building_id} onSelect={setSel} />}</Q>
          <div className="mt-3 flex flex-wrap items-center gap-4 px-2 text-xs text-ink2">
            {LEGEND.map(([c, l]) => <span key={l} className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full" style={{ background: c }} />{l}</span>)}
            <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full border-[3px] border-blue-600 bg-white" />Simulated solar asset</span>
          </div>
        </Card>
        <Card title={sel ? sel.building : "Building details"} subtitle={sel ? `${sel.zone} · ${sel.building_type.replaceAll("_", " ")}` : "Select a building on the map"}>
          {!sel ? <Empty text="Click a marker" /> : <Q q={det} h={400}>{(d: any) => (
            <div className="space-y-4 text-sm">
              <div className="flex items-center justify-between"><span>Status</span><Badge kind={sel.status}>{sel.status}</Badge></div>
              <dl className="grid grid-cols-2 gap-3">
                <div><dt className="text-xs text-ink2">Current consumption</dt><dd className="font-semibold">{n1(sel.current_kw)} kW</dd></div>
                <div><dt className="text-xs text-ink2">Expected (comparable hours)</dt><dd className="font-semibold">{n1(sel.expected_kw)} kW</dd></div>
                <div><dt className="text-xs text-ink2">7-day energy</dt><dd className="font-semibold">{n0(sel.kwh)} kWh</dd></div>
                <div><dt className="text-xs text-ink2">Predicted next hour</dt><dd className="font-semibold">{n1(d.forecast[0]?.kw)} kW</dd></div>
              </dl>
              <div><p className="mb-1 text-xs font-medium text-ink2">Historical consumption (kWh/day)</p>
                <LineSeries data={d.daily} x="bucket" series={[{ key: "kwh", label: "Energy", color: "#2a78d6" }]} unit="kWh" height={150} /></div>
              <div><p className="mb-1 text-xs font-medium text-ink2">Anomalies</p>{d.anomalies.length ? d.anomalies.slice(0, 3).map((a: any) => <p key={a.id} className="text-xs">{ist(a.timestamp)} · <Badge kind={a.severity}>{a.severity}</Badge> +{n0(a.deviation)}%</p>) : <p className="text-xs text-muted">None recorded</p>}</div>
              <div><p className="mb-1 text-xs font-medium text-ink2">Recommendations</p>{d.recommendations.length ? d.recommendations.slice(0, 3).map((r: any) => <p key={r.id} className="text-xs">• {r.title}</p>) : <p className="text-xs text-muted">None</p>}</div>
              <Link href={`/buildings/${sel.building_id}`} className="inline-block rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-white">Open building analytics</Link>
            </div>)}</Q>}
        </Card>
      </div>
    </>
  );
}
