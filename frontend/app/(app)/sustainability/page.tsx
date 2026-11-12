"use client";
import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Cloud, Leaf, Sun, TrendingDown } from "lucide-react";
import { api } from "@/lib/api";
import { Card, Kpi, Note, PageHeader, Q, Select } from "@/components/ui";
import { Bars } from "@/components/charts";
import { compact, n0, n2, ZONE_COLOR } from "@/lib/format";

export default function Sustainability() {
  const [days, setDays] = useState("30");
  const q = useQuery({ queryKey: ["sust", days], queryFn: () => api("/api/reports/sustainability?days=" + days) });
  return (
    <>
      <PageHeader title="Sustainability Analytics" desc="Carbon = grid electricity × emissions factor. The factor is a configurable assumption - set it from an official source in System Configuration."
        right={<Select label="Period" value={days} onChange={setDays} options={["7", "30", "60", "90"].map((v) => ({ value: v, label: `Last ${v} days` }))} />} />
      <Q q={q} h={300}>{(d: any) => (<>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Kpi label="Estimated emissions" value={`${compact(d.estimated_emissions_kg / 1000)} tCO₂e`} icon={<Cloud className="h-4 w-4" />} sub={`factor ${d.emissions_factor_kg_per_kwh} kg/kWh (assumption)`} tone="warn" />
          <Kpi label="Renewable energy (simulated)" value={`${n0(d.renewable_kwh)} kWh`} icon={<Sun className="h-4 w-4" />} tone="good" />
          <Kpi label="Estimated emissions avoided" value={`${n2(d.estimated_avoided_kg / 1000)} tCO₂e`} icon={<Leaf className="h-4 w-4" />} tone="good" sub="from simulated solar" />
          <Kpi label="Measured vs estimated savings" value={`${n0(d.measured_savings_kwh)} / ${n0(d.estimated_saving_pipeline_kwh)} kWh`} icon={<TrendingDown className="h-4 w-4" />} sub="measured / estimated pipeline" />
        </div>
        <div className="mt-6 grid gap-4 xl:grid-cols-2">
          <Card title="Zone-wise emissions (estimate)" subtitle="kg CO₂e"><Bars data={d.zone_emissions} x="zone" series={[{ key: "emissions_kg", label: "Emissions", color: "#0b1730" }]} unit="kg" /></Card>
          <Card title="Weekly energy trend" subtitle="Campus kWh per ISO week"><Bars data={d.weekly_kwh} x="week" series={[{ key: "kwh", label: "Energy", color: "#2a78d6" }]} /></Card>
        </div>
        <div className="mt-4 space-y-2"><Note>{d.formula}. {d.renewable_note}</Note>
          <Note tone="warn">All carbon figures are ESTIMATES based on the selected emissions factor. Edit it under <Link className="underline" href="/settings">System Configuration</Link>.</Note></div>
      </>)}</Q>
    </>
  );
}
