"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Download } from "lucide-react";
import { api, downloadCsv } from "@/lib/api";
import { Btn, Card, Note, PageHeader, Q, Select, Table, Td } from "@/components/ui";

const REPORTS = [
  { v: "energy", label: "Energy consumption (daily by zone)" }, { v: "buildings", label: "Building-wise energy & intensity" },
  { v: "sustainability", label: "Sustainability (zone emissions)" }, { v: "models", label: "Model evaluation" },
];
export default function Reports() {
  const [rep, setRep] = useState("energy"); const [days, setDays] = useState("30"); const [busy, setBusy] = useState(false);
  const q = useQuery({ queryKey: ["rep", rep, days], queryFn: () => api(`/api/reports/${rep}?days=${days}`) });
  const dl = async () => {
    setBusy(true);
    try { const sz = await downloadCsv(`/api/reports/${rep}?format=csv&days=${days}`, `gridwise_${rep}_${days}d.csv`); toast.success(`CSV exported (${(sz / 1024).toFixed(1)} KB)`); }
    catch (e: any) { toast.error(e.message); } finally { setBusy(false); }
  };
  return (
    <>
      <PageHeader title="Reports & Exports" desc="Preview a report and export it as CSV. Every export carries a header line identifying data as simulated. PDF export is not implemented."
        right={<>
          <Select label="Report" value={rep} onChange={setRep} options={REPORTS.map((r) => ({ value: r.v, label: r.label }))} />
          <Select label="Period" value={days} onChange={setDays} options={["7", "30", "60", "90"].map((v) => ({ value: v, label: `Last ${v} days` }))} />
          <Btn onClick={dl} disabled={busy} data-testid="export-csv"><Download className="h-4 w-4" />Export CSV</Btn>
        </>} />
      <Q q={q} h={300}>{(d: any) => {
        const meta = Object.entries(d).filter(([k, v]) => k !== "rows" && ["string", "number"].includes(typeof v));
        const rows: any[] = d.rows || []; const cols = rows[0] ? Object.keys(rows[0]) : [];
        return (<>
          <Card title="Summary"><dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2 xl:grid-cols-3">{meta.map(([k, v]) => <div key={k}><dt className="text-xs text-ink2">{k.replaceAll("_", " ")}</dt><dd className="font-medium">{typeof v === "number" ? Number(v).toLocaleString("en-IN", { maximumFractionDigits: 2 }) : String(v)}</dd></div>)}</dl></Card>
          <Card className="mt-4" title={`Rows (${rows.length})`}>
            <div className="max-h-[420px] overflow-auto"><Table head={cols}>{rows.slice(0, 200).map((r, i) => <tr key={i}>{cols.map((c) => <Td key={c}>{typeof r[c] === "number" ? Number(r[c]).toLocaleString("en-IN", { maximumFractionDigits: 2 }) : String(r[c] ?? "-")}</Td>)}</tr>)}</Table></div>
            {rows.length > 200 && <p className="mt-2 text-xs text-muted">Showing first 200 rows; the CSV contains all rows.</p>}
          </Card>
          <div className="mt-4"><Note tone="warn">Estimated savings are not measured savings. Report figures derive from SIMULATED data unless the source filter says otherwise.</Note></div>
        </>);
      }}</Q>
    </>
  );
}
