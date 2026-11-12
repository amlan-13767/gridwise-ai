"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, isAdmin, getUser } from "@/lib/api";
import { Btn, Card, Note, PageHeader, Q, Table, Td } from "@/components/ui";
import { ist } from "@/lib/format";
import CampusConfig from "@/components/dashboard/CampusConfig";

const FIELDS: [string, string, string][] = [
  ["grid_emissions_factor", "Grid emissions factor (kg CO₂e / kWh)", "Assumption: replace with an official value"],
  ["electricity_tariff", "Flat electricity tariff (₹ / kWh)", "Fallback; slab tariffs below take precedence"],
  ["reporting_period_days", "Default reporting period (days)", ""], ["operating_start_hour", "Academic operating start hour (0-23)", "Used by cooling analysis"],
  ["operating_end_hour", "Academic operating end hour (0-23)", ""], ["setback_min_fraction", "Cooling setback floor (0-1)", "Minimum fraction of cooling kept when unoccupied"],
];
export default function Settings() {
  const user = getUser(); const admin = isAdmin(user); const qc = useQueryClient();
  const s = useQuery({ queryKey: ["settings"], queryFn: () => api("/api/settings") });
  const logs = useQuery({ queryKey: ["audit"], queryFn: () => api("/api/audit-logs?limit=25"), enabled: admin });
  const [edits, setEdits] = useState<Record<string, string>>({});
  const v: Record<string, string> = { ...(s.data?.settings || {}), ...edits };
  const save = useMutation({ mutationFn: () => api("/api/settings", { method: "PATCH", body: Object.fromEntries(FIELDS.map(([k]) => [k, v[k]])) }), onSuccess: () => { toast.success("Settings saved"); qc.invalidateQueries(); }, onError: (e: any) => toast.error(e.message) });
  return (
    <>
      <PageHeader title="System Configuration" desc="Emission factor, tariffs and operating assumptions drive cost, carbon and cooling estimates. Only a Super Administrator can change them; every change is audit-logged." />
      <Q q={s}>{(d: any) => (<>
        <Card title="Parameters" subtitle={d.notes}>
          <div className="grid gap-4 sm:grid-cols-2">{FIELDS.map(([k, l, h]) => (<label key={k} className="text-xs text-ink2">{l}<input value={v[k] ?? ""} onChange={(e) => setEdits({ ...edits, [k]: e.target.value })} disabled={!admin} data-testid={`set-${k}`}
            className="mt-1 block w-full rounded-lg border border-line px-3 py-2 text-sm text-ink disabled:bg-slate-50" /><span className="text-[11px] text-muted">{h}</span></label>))}</div>
          {admin ? <Btn className="mt-4" onClick={() => save.mutate()} disabled={save.isPending}>Save changes</Btn> : <p className="mt-4 text-xs text-muted">Read-only for your role.</p>}
        </Card>
        <Card className="mt-6" title="Electricity tariff slabs (assumptions)"><Table head={["Name", "From", "To", "₹ / kWh", "Basis"]}>{d.tariffs.map((t: any) => <tr key={t.id}><Td>{t.name}</Td><Td>{t.start_hour}:00</Td><Td>{t.end_hour}:00</Td><Td>{t.rate}</Td><Td>{t.assumption ? "assumption" : "official"}</Td></tr>)}</Table></Card>
        <Card className="mt-6" title="Data mode"><p className="text-sm">{d.settings.data_mode}</p><div className="mt-2"><Note>Control capability is disabled by design: the platform monitors and recommends only.</Note></div></Card>
      </>)}</Q>
      {admin && <CampusConfig />}
      {admin && <Card className="mt-6" title="Recent audit log"><Q q={logs}>{(d: any) => <Table head={["When (IST)", "User", "Action", "Entity"]}>{d.items.map((a: any) => <tr key={a.id}><Td>{ist(a.at)}</Td><Td>{a.user || "system"}</Td><Td>{a.action}</Td><Td>{a.entity} {a.entity_id}</Td></tr>)}</Table>}</Q></Card>}
    </>
  );
}
