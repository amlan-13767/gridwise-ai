"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, getUser, qs } from "@/lib/api";
import { Badge, Btn, Card, Empty, Note, PageHeader, Q, Select, Table, Td } from "@/components/ui";
import { LineSeries } from "@/components/charts";
import { ist, istHour, n0, n1 } from "@/lib/format";

export default function Anomalies() {
  const user = getUser(); const qc = useQueryClient();
  const [status, setStatus] = useState("open"); const [sev, setSev] = useState("all"); const [zone, setZone] = useState("all"); const [days, setDays] = useState("30");
  const [sel, setSel] = useState<number | null>(null); const [note, setNote] = useState("");
  const list = useQuery({ queryKey: ["anoms", status, sev, zone, days], queryFn: () => api("/api/anomalies" + qs({ status, severity: sev, zone, days, limit: 60 })) });
  const det = useQuery({ queryKey: ["anom", sel], queryFn: () => api("/api/anomalies/" + sel), enabled: !!sel });
  const ev = useQuery({ queryKey: ["anom-ev"], queryFn: () => api("/api/anomalies-evaluation") });
  const review = useMutation({ mutationFn: (s: string) => api(`/api/anomalies/${sel}/review`, { method: "PATCH", body: { status: s, note: note || undefined } }),
    onSuccess: () => { toast.success("Review saved"); qc.invalidateQueries({ queryKey: ["anoms"] }); qc.invalidateQueries({ queryKey: ["anom", sel] }); setNote(""); }, onError: (e: any) => toast.error(e.message) });
  const canReview = user && user.role !== "viewer";
  return (
    <>
      <PageHeader title="Anomaly Detection" desc="Hourly consumption compared with comparable hours (same hour of day, weekday vs weekend) using a robust z-score, rolling-mean jumps and Isolation Forest. An anomaly is an investigation lead - not confirmed wastage."
        right={<>
          <Select label="Status" value={status} onChange={setStatus} options={[{ value: "all", label: "Any" }, ...["open", "investigating", "resolved", "dismissed"].map((v) => ({ value: v, label: v }))]} />
          <Select label="Severity" value={sev} onChange={setSev} options={[{ value: "all", label: "Any" }, ...["critical", "high", "medium", "low"].map((v) => ({ value: v, label: v }))]} />
          <Select label="Zone" value={zone} onChange={setZone} options={[{ value: "all", label: "All" }, ...["Academic", "Hostel", "Residential"].map((v) => ({ value: v, label: v }))]} />
          <Select label="Window" value={days} onChange={setDays} options={["7", "30", "90"].map((v) => ({ value: v, label: `${v} days` }))} />
        </>} />
      <div className="grid gap-4 xl:grid-cols-5">
        <Card className="xl:col-span-3" title={`Detected anomalies${list.data ? ` (${list.data.total})` : ""}`}>
          <Q q={list}>{(d: any) => d.items.length ? <Table head={["Building", "Time (IST)", "Observed", "Expected", "Deviation", "Severity", "Status"]}>
            {d.items.map((a: any) => (<tr key={a.id} onClick={() => setSel(a.id)} className={`cursor-pointer hover:bg-slate-50 ${sel === a.id ? "bg-blue-50" : ""}`} data-testid="anomaly-row">
              <Td>{a.building}</Td><Td>{ist(a.timestamp)}</Td><Td>{n1(a.observed_kw)} kW</Td><Td>{n1(a.expected_kw)} kW</Td><Td>+{n0(a.deviation_pct)}%</Td><Td><Badge kind={a.severity}>{a.severity}</Badge></Td><Td><Badge kind={a.status}>{a.status}</Badge></Td></tr>))}
          </Table> : <Empty text="No anomalies for these filters" />}</Q>
        </Card>
        <Card className="xl:col-span-2" title={det.data ? `${det.data.building}: ${det.data.category.replaceAll("_", " ")}` : "Anomaly detail"} subtitle={det.data ? ist(det.data.timestamp) + " IST" : "Select a row"}>
          {!sel ? <Empty text="Select an anomaly to inspect it" /> : <Q q={det} h={360}>{(a: any) => (
            <div className="space-y-4 text-sm">
              <LineSeries data={a.context.map((c: any) => ({ t: istHour(c.ts), kw: c.kw }))} x="t" series={[{ key: "kw", label: "Building demand", color: "#2a78d6" }]} height={180} />
              <dl className="grid grid-cols-2 gap-2 text-xs">
                <div><dt className="text-ink2">Detection method</dt><dd className="font-medium">{a.detection_method.replaceAll("_", " ")}</dd></div>
                <div><dt className="text-ink2">Deviation</dt><dd className="font-medium">+{n0(a.deviation_pct)}% ({a.severity})</dd></div>
                <div><dt className="text-ink2">Historical baseline</dt><dd className="font-medium">{a.baseline?.day_type} · {String(a.baseline?.hour_local).padStart(2, "0")}:00 · σ≈{n1(a.baseline?.robust_sigma_kw)} kW</dd></div>
                <div><dt className="text-ink2">z-score</dt><dd className="font-medium">{n1(a.baseline?.z_score)}</dd></div>
              </dl>
              <Note>{a.recommended_investigation}</Note>
              <Note tone="warn">{a.disclaimer}</Note>
              {canReview && <div className="space-y-2"><input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Review note (optional)" className="w-full rounded-lg border border-line px-3 py-1.5 text-sm" />
                <div className="flex flex-wrap gap-2"><Btn onClick={() => review.mutate("investigating")}>Mark investigating</Btn><Btn variant="good" onClick={() => review.mutate("resolved")}>Resolved</Btn><Btn variant="ghost" onClick={() => review.mutate("dismissed")}>Dismiss</Btn></div></div>}
              {a.review_note && <p className="text-xs text-ink2">Note: {a.review_note}</p>}
            </div>)}</Q>}
        </Card>
      </div>
      <Card className="mt-6" title="Detector evaluation" subtitle="Against injected SIMULATED anomalies at hourly granularity">
        <Q q={ev}>{(r: any) => <p className="text-sm text-ink2">Flags: <b>{r.total_flags}</b> · precision <b>{(r.precision * 100).toFixed(1)}%</b> · recall <b>{(r.recall * 100).toFixed(1)}%</b> (TP {r.tp}, FP {r.fp}, FN {r.fn}). Real-world performance will differ and needs tuning on authorised meter data.</p>}</Q>
      </Card>
    </>
  );
}
