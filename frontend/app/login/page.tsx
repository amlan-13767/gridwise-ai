"use client";
import { useRouter } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Zap } from "lucide-react";
import Link from "next/link";
import { api, setSession } from "@/lib/api";
import { Btn, Spinner } from "@/components/ui";

const schema = z.object({ email: z.string().email("Enter a valid email"), password: z.string().min(1, "Password required") });
type F = z.infer<typeof schema>;
const DEMO = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
const DEMO_PW = process.env.NEXT_PUBLIC_DEMO_PASSWORD || "";
const ACCOUNTS = [
  { label: "Administrator", email: "admin@gridwise.demo" }, { label: "Facilities Manager", email: "manager@gridwise.demo" },
  { label: "Zone Manager (Hostel)", email: "zone@gridwise.demo" }, { label: "Auditor / Viewer", email: "viewer@gridwise.demo" },
];

export default function Login() {
  const router = useRouter(); const [busy, setBusy] = useState(false);
  // false during SSR/hydration, true afterwards: the submit button stays disabled until the React handler is attached,
  // otherwise an early click would fall back to a native form submission
  const hydrated = useSyncExternalStore(() => () => {}, () => true, () => false);
  const { register, handleSubmit, setValue, formState: { errors } } = useForm<F>({ resolver: zodResolver(schema) });
  const submit = async (v: F) => {
    setBusy(true);
    const wake = setTimeout(() => toast.info("Waking the demo server… the free hosting tier can take up to a minute after inactivity.", { id: "wake", duration: 60000 }), 4000);
    try { const r = await api("/api/auth/login", { method: "POST", body: v }); setSession(r.access_token, r.user); toast.dismiss("wake"); toast.success(`Welcome, ${r.user.name}`); router.push("/dashboard"); }
    catch (e: any) { toast.dismiss("wake"); toast.error(e.message || "Login failed"); } finally { clearTimeout(wake); setBusy(false); }
  };
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-navy p-12 text-white lg:flex">
        <Link href="/" className="flex items-center gap-2"><span className="grid h-9 w-9 place-items-center rounded-xl bg-primary"><Zap className="h-5 w-5" /></span><b>GRIDWISE AI</b></Link>
        <div><h2 className="text-3xl font-semibold leading-tight">Campus energy,<br />understood and optimised.</h2><p className="mt-4 max-w-md text-slate-300">Forecast demand, catch anomalies, trim cooling waste and plan around solar - across Academic, Hostel and Residential zones.</p></div>
        <p className="text-xs text-slate-400">Demonstration environment · simulated data only</p>
      </div>
      <div className="grid place-items-center p-6">
        <form method="post" onSubmit={handleSubmit(submit)} className="w-full max-w-sm space-y-4" noValidate>
          <h1 className="text-2xl font-semibold">Sign in</h1>
          <p className="text-sm text-ink2">Accounts are created by an administrator. There is no public sign-up.</p>
          <div><label className="text-xs font-medium text-ink2" htmlFor="email">Email</label>
            <input id="email" type="email" autoComplete="username" {...register("email")} className="mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm outline-none focus:border-primary" />
            {errors.email && <p className="mt-1 text-xs text-bad">{errors.email.message}</p>}</div>
          <div><label className="text-xs font-medium text-ink2" htmlFor="password">Password</label>
            <input id="password" type="password" autoComplete="current-password" {...register("password")} className="mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm outline-none focus:border-primary" />
            {errors.password && <p className="mt-1 text-xs text-bad">{errors.password.message}</p>}</div>
          <Btn type="submit" disabled={busy || !hydrated} className="w-full justify-center py-2.5">{busy && <Spinner />}Sign in</Btn>
          {DEMO && DEMO_PW && (
            <div className="rounded-xl border border-dashed border-line p-3">
              <p className="mb-2 text-xs font-medium text-ink2">Demo accounts (simulated environment)</p>
              <div className="grid grid-cols-2 gap-2">{ACCOUNTS.map((a) => <button type="button" key={a.email} data-testid={`demo-${a.label.split(" ")[0].toLowerCase()}`} onClick={() => { setValue("email", a.email); setValue("password", DEMO_PW); }} className="rounded-lg bg-slate-50 px-2 py-1.5 text-xs hover:bg-slate-100">{a.label}</button>)}</div>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
