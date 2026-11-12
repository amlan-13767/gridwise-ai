"use client";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { SERIES, ZONE_COLOR, n1 } from "@/lib/format";

const axis = { stroke: "#94a3b8", fontSize: 11, tickLine: false, axisLine: false } as const;
const tip = { contentStyle: { borderRadius: 10, border: "1px solid #e2e8f0", fontSize: 12, boxShadow: "0 4px 14px rgba(15,23,42,.08)" }, formatter: (v: any) => (typeof v === "number" ? n1(v) : v) };
export type S = { key: string; label: string; color?: string };

export function colorFor(label: string, i: number) { return ZONE_COLOR[label] || SERIES[i % SERIES.length]; }

export function LineSeries({ data, x, series, height = 260, unit = "kW", dash }: { data: any[]; x: string; series: S[]; height?: number; unit?: string; dash?: string[] }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ left: -8, right: 8, top: 6 }}>
        <CartesianGrid stroke="#eef2f7" vertical={false} />
        <XAxis dataKey={x} {...axis} minTickGap={32} /><YAxis {...axis} width={52} unit={""} />
        <Tooltip {...tip} /><Legend wrapperStyle={{ fontSize: 12 }} />
        {series.map((s, i) => <Line key={s.key} type="monotone" dataKey={s.key} name={`${s.label} (${unit})`} stroke={s.color || colorFor(s.label, i)} strokeWidth={2} dot={false} strokeDasharray={dash?.[i]} connectNulls />)}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function BandChart({ data, x, height = 280 }: { data: any[]; x: string; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ left: -8, right: 8, top: 6 }}>
        <CartesianGrid stroke="#eef2f7" vertical={false} />
        <XAxis dataKey={x} {...axis} minTickGap={36} /><YAxis {...axis} width={52} />
        <Tooltip {...tip} /><Legend wrapperStyle={{ fontSize: 12 }} />
        <Area type="monotone" dataKey="band" name="80% interval (kW)" stroke="none" fill="#2a78d6" fillOpacity={0.14} />
        <Line type="monotone" dataKey="actual" name="Actual (kW)" stroke="#0b1730" strokeWidth={2} dot={false} connectNulls />
        <Line type="monotone" dataKey="kw" name="Forecast (kW)" stroke="#2a78d6" strokeWidth={2.2} strokeDasharray="5 3" dot={false} connectNulls />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function StackedArea({ data, x, series, height = 260, unit = "kWh" }: { data: any[]; x: string; series: S[]; height?: number; unit?: string }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ left: -8, right: 8, top: 6 }}>
        <CartesianGrid stroke="#eef2f7" vertical={false} />
        <XAxis dataKey={x} {...axis} minTickGap={32} /><YAxis {...axis} width={56} />
        <Tooltip {...tip} /><Legend wrapperStyle={{ fontSize: 12 }} />
        {series.map((s, i) => <Area key={s.key} type="monotone" stackId="1" dataKey={s.key} name={`${s.label} (${unit})`} stroke={s.color || colorFor(s.label, i)} fill={s.color || colorFor(s.label, i)} fillOpacity={0.75} strokeWidth={1.5} />)}
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function Bars({ data, x, series, height = 260, stacked, layout = "horizontal", unit = "kWh" }: { data: any[]; x: string; series: S[]; height?: number; stacked?: boolean; layout?: "horizontal" | "vertical"; unit?: string }) {
  const v = layout === "vertical";
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout={layout} margin={{ left: v ? 40 : -8, right: 8, top: 6 }}>
        <CartesianGrid stroke="#eef2f7" horizontal={!v} vertical={v} />
        {v ? <><XAxis type="number" {...axis} /><YAxis type="category" dataKey={x} {...axis} width={150} /></> : <><XAxis dataKey={x} {...axis} minTickGap={20} /><YAxis {...axis} width={56} /></>}
        <Tooltip {...tip} cursor={{ fill: "#f1f5f9" }} />{series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
        {series.map((s, i) => <Bar key={s.key} dataKey={s.key} name={`${s.label} (${unit})`} stackId={stacked ? "1" : undefined} fill={s.color || colorFor(s.label, i)} radius={stacked ? 0 : [4, 4, 0, 0]} maxBarSize={36} />)}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** pivot [{bucket, <groupKey>, kwh}] into wide rows */
export function pivot(rows: any[], groupKey: string, valueKey = "kwh", bucketKey = "bucket") {
  const m = new Map<string, any>(); const keys = new Set<string>();
  rows.forEach((r) => { const o = m.get(r[bucketKey]) || { [bucketKey]: r[bucketKey] }; o[r[groupKey]] = r[valueKey]; keys.add(r[groupKey]); m.set(r[bucketKey], o); });
  return { data: [...m.values()], keys: [...keys] };
}
