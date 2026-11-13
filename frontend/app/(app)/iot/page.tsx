"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Cpu } from "lucide-react";
import { api, getUser, isAdmin } from "@/lib/api";
import { Badge, Btn, Card, Kpi, Note, PageHeader, Q, Table, Td } from "@/components/ui";
import { ist } from "@/lib/format";

const schema = z.object({ building_id: z.coerce.number().int().positive("Pick a building"), meter_identifier: z.string().min(3, "At least 3 characters").max(50),
  communication_protocol: z.enum(["mqtt", "modbus_tcp", "modbus_rtu", "http", "manual"]), installation_location: z.string().max(150).optional(), data_source: z.enum(["real", "simulated"]) });
type F = z.input<typeof schema>;

export default function Iot() {
  const user = getUser(); const qc = useQueryClient(); const [key, setKey] = useState<{ id: string; key: string } | null>(null);
  const dev = useQuery({ queryKey: ["devs"], queryFn: () => api("/api/iot/devices") });
  const st = useQuery({ queryKey: ["iot-st"], queryFn: () => api("/api/iot/status") });
  const blds = useQuery({ queryKey: ["blds-all"], queryFn: () => api("/api/buildings?limit=200") });
  const { register, handleSubmit, reset, formState: { errors } } = useForm<F>({ resolver: zodResolver(schema) as any, defaultValues: { communication_protocol: "mqtt", data_source: "real" } });
  const add = useMutation({ mutationFn: (b: any) => api("/api/iot/devices", { method: "POST", body: b }), onSuccess: (r: any) => { toast.success("Device registered"); setKey({ id: r.meter_identifier, key: r.device_key }); reset(); qc.invalidateQueries({ queryKey: ["devs"] }); }, onError: (e: any) => toast.error(e.message) });
  const patch = useMutation({ mutationFn: (a: { id: number; status: string }) => api(`/api/iot/devices/${a.id}`, { method: "PATCH", body: { status: a.status } }), onSuccess: () => { toast.success("Device updated"); qc.invalidateQueries({ queryKey: ["devs"] }); }, onError: (e: any) => toast.error(e.message) });
  return (
    <>
      <PageHeader title="IoT Device Management" desc="Devices publish validated readings over MQTT (topic gridwise/campus/<zone>/<building>/<meter>) or HTTP. Each device authenticates with its own key; duplicates, delayed and out-of-range messages are handled." />
      <Q q={st} h={90}>{(s: any) => <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Registered devices" value={s.devices} icon={<Cpu className="h-4 w-4" />} />
        {Object.entries(s.by_connection).map(([k, v]: any) => <Kpi key={k} label={k.replaceAll("_", " ")} value={v} tone={k === "online" ? "good" : k === "offline" ? "bad" : "default"} />)}
      </div>}</Q>
      <Card className="mt-6" title="Devices" subtitle="Simulated devices are virtual; no real hardware is implied. Connection status is relative to the newest reading.">
        <Q q={dev}>{(d: any) => <div className="max-h-[420px] overflow-auto"><Table head={["Meter / device", "Building", "Zone", "Protocol", "Source", "Connection", "Last seen (IST)", "Config", ""]}>
          {d.items.map((m: any) => (<tr key={m.id}><Td>{m.meter_identifier}</Td><Td>{m.building}</Td><Td>{m.zone}</Td><Td>{m.protocol}</Td><Td><Badge kind={m.data_source}>{m.data_source}</Badge></Td>
            <Td><Badge kind={m.connection}>{m.connection}</Badge></Td><Td>{m.last_seen ? ist(m.last_seen) : "-"}</Td><Td>{m.config_status}</Td>
            <Td>{isAdmin(user) && <Btn variant="ghost" onClick={() => patch.mutate({ id: m.id, status: m.config_status === "active" ? "maintenance" : "active" })}>{m.config_status === "active" ? "Set maintenance" : "Activate"}</Btn>}</Td></tr>))}</Table></div>}</Q>
      </Card>
      {isAdmin(user) && <Card className="mt-6" title="Register a device" subtitle="Only authorised, professionally installed certified meters should be connected. Never connect development boards to mains.">
        <form method="post" onSubmit={handleSubmit((v) => add.mutate(v))} className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" noValidate>
          <label className="text-xs text-ink2">Building<select {...register("building_id")} className="mt-1 block w-full rounded-lg border border-line px-2 py-1.5 text-sm text-ink"><option value="">Select…</option>{(blds.data?.items || []).map((b: any) => <option key={b.id} value={b.id}>{b.building_name}</option>)}</select>{errors.building_id && <span className="text-bad">{errors.building_id.message}</span>}</label>
          <label className="text-xs text-ink2">Device identifier<input {...register("meter_identifier")} placeholder="MTR-XXX-01" className="mt-1 block w-full rounded-lg border border-line px-2 py-1.5 text-sm text-ink" />{errors.meter_identifier && <span className="text-bad">{errors.meter_identifier.message}</span>}</label>
          <label className="text-xs text-ink2">Protocol<select {...register("communication_protocol")} className="mt-1 block w-full rounded-lg border border-line px-2 py-1.5 text-sm text-ink">{["mqtt", "modbus_tcp", "modbus_rtu", "http", "manual"].map((p) => <option key={p}>{p}</option>)}</select></label>
          <label className="text-xs text-ink2">Data source<select {...register("data_source")} className="mt-1 block w-full rounded-lg border border-line px-2 py-1.5 text-sm text-ink"><option value="real">real</option><option value="simulated">simulated</option></select></label>
          <label className="text-xs text-ink2 sm:col-span-1">Installation location<input {...register("installation_location")} className="mt-1 block w-full rounded-lg border border-line px-2 py-1.5 text-sm text-ink" /></label>
          <div className="flex items-end"><Btn type="submit" disabled={add.isPending}>Register device</Btn></div>
        </form>
        {key && <div className="mt-4"><Note tone="warn">Device key for <b>{key.id}</b> (shown once, store securely): <code className="break-all">{key.key}</code></Note></div>}
      </Card>}
      <div className="mt-6 grid gap-4 xl:grid-cols-2">
        <Card title="Example MQTT payload"><pre className="overflow-x-auto rounded-lg bg-slate-50 p-3 text-xs">{`topic: gridwise/campus/academic/building-a/meter-01\n{\n  "meter_id": "MTR-ACD-01",\n  "timestamp": "2026-11-13T10:00:00Z",\n  "power_kw": 18.5,\n  "energy_kwh": 4.62,\n  "voltage": 230, "current": 12.4,\n  "source": "simulated",\n  "device_key": "<per-device key>"\n}`}</pre></Card>
        <Card title="Run the simulator"><pre className="overflow-x-auto rounded-lg bg-slate-50 p-3 text-xs">{`python iot/simulators/simulator.py --mode http --count 3\npython iot/simulators/simulator.py --mode mqtt --broker localhost`}</pre><p className="mt-2 text-xs text-ink2">Messages are labelled source=simulated and are rejected if the meter is registered as real.</p></Card>
      </div>
    </>
  );
}
