"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, getUser, isAdmin } from "@/lib/api";
import { Badge, Btn, Card, Note, PageHeader, Q, Table, Td } from "@/components/ui";
import { ist, n2 } from "@/lib/format";

export default function Models() {
  const user = getUser(); const qc = useQueryClient(); const [open, setOpen] = useState<number | null>(null);
  const q = useQuery({ queryKey: ["models"], queryFn: () => api("/api/models") });
  const rev = useMutation({ mutationFn: (a: { id: number; decision: string }) => api(`/api/models/${a.id}/review`, { method: "POST", body: { decision: a.decision } }), onSuccess: () => { toast.success("Model status updated"); qc.invalidateQueries({ queryKey: ["models"] }); }, onError: (e: any) => toast.error(e.message) });
  return (
    <>
      <PageHeader title="Model Management" desc="Trained models stay 'pending review' until a Super Administrator reviews the evaluation report and promotes them. No unreviewed model replacement happens in production." />
      <Q q={q} h={300}>{(d: any) => (<Card>
        <Table head={["Model", "Version", "Task", "Trained (IST)", "Dataset", "Status", "Last prediction", "Test RMSE", "Baseline RMSE", ""]}>
          {d.items.map((m: any) => (<tr key={m.id}><Td>{m.name}</Td><Td>{m.version}</Td><Td>{m.task.replaceAll("_", " ")}</Td><Td>{ist(m.trained_at)}</Td><Td className="max-w-[200px] truncate">{m.training_dataset}</Td>
            <Td><Badge kind={m.status}>{m.status}</Badge></Td><Td>{m.last_prediction_at ? ist(m.last_prediction_at) : "-"}</Td>
            <Td>{m.metrics?.test?.rmse != null ? n2(m.metrics.test.rmse) : "-"}</Td><Td>{m.metrics?.baseline?.rmse != null ? n2(m.metrics.baseline.rmse) : "-"}</Td>
            <Td><div className="flex gap-2"><Btn variant="ghost" onClick={() => setOpen(open === m.id ? null : m.id)}>Report</Btn>
              {isAdmin(user) && m.status !== "production" && <Btn variant="good" onClick={() => rev.mutate({ id: m.id, decision: "promote" })}>Promote</Btn>}
              {isAdmin(user) && m.status === "pending_review" && <Btn variant="ghost" onClick={() => rev.mutate({ id: m.id, decision: "reject" })}>Reject</Btn>}</div></Td></tr>))}
        </Table>
        {open && <pre className="mt-4 max-h-96 overflow-auto rounded-lg bg-slate-50 p-3 text-xs">{JSON.stringify(d.items.find((m: any) => m.id === open)?.metrics, null, 2)}</pre>}
      </Card>)}</Q>
      <div className="mt-4"><Note tone="warn">All metrics were measured on SIMULATED data. They do not predict accuracy on real NIT Rourkela meters; retrain and re-evaluate on authorised real data before relying on them.</Note></div>
    </>
  );
}
