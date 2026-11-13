"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api } from "@/lib/api";
import { Badge, Btn, Card, Note, PageHeader, Q, Table, Td } from "@/components/ui";

const schema = z.object({ name: z.string().min(2), email: z.string().email(), password: z.string().min(10, "Min 10 characters"),
  role: z.enum(["super_admin", "energy_manager", "zone_manager", "viewer"]), assigned_zone_id: z.string().optional() });
type F = z.infer<typeof schema>;

export default function Users() {
  const qc = useQueryClient();
  const users = useQuery({ queryKey: ["users"], queryFn: () => api("/api/users") });
  const zones = useQuery({ queryKey: ["zones"], queryFn: () => api("/api/zones") });
  const { register, handleSubmit, reset, watch, formState: { errors } } = useForm<F>({ resolver: zodResolver(schema), defaultValues: { role: "viewer" } });
  const create = useMutation({ mutationFn: (v: F) => api("/api/auth/register", { method: "POST", body: { ...v, assigned_zone_id: v.assigned_zone_id ? Number(v.assigned_zone_id) : null } }), onSuccess: () => { toast.success("User created"); reset(); qc.invalidateQueries({ queryKey: ["users"] }); }, onError: (e: any) => toast.error(e.message) });
  const patch = useMutation({ mutationFn: (a: { id: number; body: any }) => api(`/api/users/${a.id}`, { method: "PATCH", body: a.body }), onSuccess: () => { toast.success("User updated"); qc.invalidateQueries({ queryKey: ["users"] }); }, onError: (e: any) => toast.error(e.message) });
  return (
    <>
      <PageHeader title="User Management" desc="Administrators create accounts; there is no public registration. Zone managers see only their assigned zone; viewers cannot see building-level residential data." />
      <Card title="Users"><Q q={users}>{(d: any) => <Table head={["Name", "Email", "Role", "Zone", "Status", ""]}>{d.items.map((u: any) => (
        <tr key={u.id}><Td>{u.name}</Td><Td>{u.email}</Td><Td>{u.role.replaceAll("_", " ")}</Td><Td>{(zones.data || []).find((z: any) => z.id === u.assigned_zone_id)?.name || "-"}</Td>
          <Td><Badge kind={u.is_active ? "online" : "offline"}>{u.is_active ? "active" : "disabled"}</Badge></Td>
          <Td><Btn variant="ghost" onClick={() => patch.mutate({ id: u.id, body: { is_active: !u.is_active } })}>{u.is_active ? "Disable" : "Enable"}</Btn></Td></tr>))}</Table>}</Q></Card>
      <Card className="mt-6" title="Create user">
        <form method="post" onSubmit={handleSubmit((v) => create.mutate(v))} className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" noValidate>
          {([["name", "Full name", "text"], ["email", "Email", "email"], ["password", "Initial password", "password"]] as const).map(([k, l, t]) => (
            <label key={k} className="text-xs text-ink2">{l}<input type={t} {...register(k)} autoComplete="off" className="mt-1 block w-full rounded-lg border border-line px-2 py-1.5 text-sm text-ink" />{errors[k] && <span className="text-bad">{errors[k]?.message as string}</span>}</label>))}
          <label className="text-xs text-ink2">Role<select {...register("role")} className="mt-1 block w-full rounded-lg border border-line px-2 py-1.5 text-sm text-ink"><option value="super_admin">Super Administrator</option><option value="energy_manager">Facilities / Energy Manager</option><option value="zone_manager">Zone Manager</option><option value="viewer">Viewer / Auditor</option></select></label>
          {watch("role") === "zone_manager" && <label className="text-xs text-ink2">Assigned zone<select {...register("assigned_zone_id")} className="mt-1 block w-full rounded-lg border border-line px-2 py-1.5 text-sm text-ink"><option value="">Select…</option>{(zones.data || []).map((z: any) => <option key={z.id} value={z.id}>{z.name}</option>)}</select></label>}
          <div className="flex items-end"><Btn type="submit" disabled={create.isPending}>Create user</Btn></div>
        </form>
      </Card>
      <div className="mt-4"><Note>Passwords are stored as bcrypt hashes. The first administrator is created from the server CLI (<code>python -m backend.app.cli create-admin</code>).</Note></div>
    </>
  );
}
