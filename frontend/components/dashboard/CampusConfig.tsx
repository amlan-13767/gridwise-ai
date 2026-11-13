"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api } from "@/lib/api";
import { Badge, Btn, Card, Q, Table, Td } from "@/components/ui";
import { n0 } from "@/lib/format";

const bSchema = z.object({ zone_id: z.coerce.number().int().positive("Select a zone"), code: z.string().min(2).max(20), building_name: z.string().min(2).max(150),
  building_type: z.string().min(2), floor_area: z.coerce.number().positive("Must be > 0").optional().or(z.literal("")), capacity: z.coerce.number().int().min(0).optional().or(z.literal("")) });
const zSchema = z.object({ name: z.string().min(2).max(100), zone_type: z.enum(["Academic", "Hostel", "Residential"]), description: z.string().optional() });

export default function CampusConfig() {
  const qc = useQueryClient(); const [filter, setFilter] = useState("");
  const zones = useQuery({ queryKey: ["zones"], queryFn: () => api("/api/zones") });
  const blds = useQuery({ queryKey: ["cfg-blds"], queryFn: () => api("/api/buildings?limit=200&include_inactive=true") });
  const bf = useForm<any>({ resolver: zodResolver(bSchema) as any }); const zf = useForm<any>({ resolver: zodResolver(zSchema) as any, defaultValues: { zone_type: "Academic" } });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["cfg-blds"] }); qc.invalidateQueries({ queryKey: ["zones"] }); qc.invalidateQueries({ queryKey: ["blds-all"] }); };
  const addB = useMutation({ mutationFn: (v: any) => api("/api/buildings", { method: "POST", body: { ...v, floor_area: v.floor_area === "" ? null : v.floor_area, capacity: v.capacity === "" ? null : v.capacity } }), onSuccess: () => { toast.success("Building added (no meter yet: add one under IoT Devices)"); bf.reset(); refresh(); }, onError: (e: any) => toast.error(e.message) });
  const addZ = useMutation({ mutationFn: (v: any) => api("/api/zones", { method: "POST", body: v }), onSuccess: () => { toast.success("Zone created"); zf.reset(); refresh(); }, onError: (e: any) => toast.error(e.message) });
  const toggle = useMutation({ mutationFn: (b: any) => api(`/api/buildings/${b.id}`, { method: "PATCH", body: { is_active: !b.is_active } }), onSuccess: () => { toast.success("Building updated"); refresh(); }, onError: (e: any) => toast.error(e.message) });
  const inp = "mt-1 block w-full rounded-lg border border-line px-2 py-1.5 text-sm text-ink";
  return (
    <Card className="mt-6" title="Campus infrastructure" subtitle="Buildings and zones are configurable data, not hard-coded. The sample records are SIMULATED, not the real NIT Rourkela inventory.">
      <div className="grid gap-6 xl:grid-cols-2">
        <form method="post" onSubmit={bf.handleSubmit((v: any) => addB.mutate(v))} className="grid gap-3 sm:grid-cols-2" noValidate>
          <p className="text-sm font-medium sm:col-span-2">Add building</p>
          <label className="text-xs text-ink2">Zone<select {...bf.register("zone_id")} className={inp}><option value="">Select…</option>{(zones.data || []).map((z: any) => <option key={z.id} value={z.id}>{z.name}</option>)}</select></label>
          <label className="text-xs text-ink2">Code<input {...bf.register("code")} placeholder="ACD-11" className={inp} /></label>
          <label className="text-xs text-ink2 sm:col-span-2">Name<input {...bf.register("building_name")} className={inp} /></label>
          <label className="text-xs text-ink2">Type<input {...bf.register("building_type")} placeholder="lecture / hostel / residential" className={inp} /></label>
          <label className="text-xs text-ink2">Floor area (m²)<input {...bf.register("floor_area")} inputMode="decimal" className={inp} /></label>
          <label className="text-xs text-ink2">Capacity<input {...bf.register("capacity")} inputMode="numeric" className={inp} /></label>
          <div className="flex items-end"><Btn type="submit" disabled={addB.isPending}>Add building</Btn></div>
          {Object.values(bf.formState.errors).length > 0 && <p className="text-xs text-bad sm:col-span-2">Check the highlighted fields: zone, code, name and type are required.</p>}
        </form>
        <form method="post" onSubmit={zf.handleSubmit((v: any) => addZ.mutate(v))} className="grid content-start gap-3 sm:grid-cols-2" noValidate>
          <p className="text-sm font-medium sm:col-span-2">Create zone</p>
          <label className="text-xs text-ink2">Name<input {...zf.register("name")} className={inp} /></label>
          <label className="text-xs text-ink2">Type<select {...zf.register("zone_type")} className={inp}>{["Academic", "Hostel", "Residential"].map((t) => <option key={t}>{t}</option>)}</select></label>
          <label className="text-xs text-ink2 sm:col-span-2">Description<input {...zf.register("description")} className={inp} /></label>
          <Btn type="submit" disabled={addZ.isPending}>Create zone</Btn>
        </form>
      </div>
      <div className="mt-6"><label className="text-xs text-ink2">Filter buildings<input value={filter} onChange={(e) => setFilter(e.target.value)} className="ml-2 rounded-lg border border-line px-2 py-1 text-sm text-ink" /></label></div>
      <Q q={blds} h={200}>{(d: any) => <div className="mt-2 max-h-72 overflow-auto"><Table head={["Code", "Name", "Zone", "Type", "Area m²", "Capacity", "Source", "Status", ""]}>
        {d.items.filter((b: any) => (b.building_name + b.code).toLowerCase().includes(filter.toLowerCase())).map((b: any) => (<tr key={b.id}><Td>{b.code}</Td><Td>{b.building_name}</Td><Td>{b.zone_type}</Td><Td>{b.building_type}</Td><Td>{n0(b.floor_area)}</Td><Td>{b.capacity ?? "-"}</Td>
          <Td><Badge kind={b.data_source}>{b.data_source}</Badge></Td><Td><Badge kind={b.is_active ? "online" : "offline"}>{b.is_active ? "active" : "inactive"}</Badge></Td>
          <Td><Btn variant="ghost" onClick={() => toggle.mutate(b)}>{b.is_active ? "Deactivate" : "Activate"}</Btn></Td></tr>))}</Table></div>}</Q>
    </Card>
  );
}
