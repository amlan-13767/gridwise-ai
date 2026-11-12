"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import { Activity, BarChart3, Bell, Building2, Cpu, FileText, Gauge, Home, Leaf, LogOut, Map, Settings, Snowflake, Sparkles, Sun, TrendingUp, Users, Workflow, Zap, Siren, Menu } from "lucide-react";
import { api, clearSession, getUser, User } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { cx } from "@/components/ui";

const NAV: { group: string; items: { href: string; label: string; icon: any; roles?: string[] }[] }[] = [
  { group: "Monitor", items: [
    { href: "/dashboard", label: "Campus Dashboard", icon: Gauge },
    { href: "/map", label: "Energy Map", icon: Map },
    { href: "/academic", label: "Academic Area", icon: Building2 },
    { href: "/hostel", label: "Hostel Area", icon: Home },
    { href: "/residential", label: "Residential Area", icon: Home },
  ] },
  { group: "Intelligence", items: [
    { href: "/forecast", label: "Demand Forecasting", icon: TrendingUp },
    { href: "/anomalies", label: "Anomaly Detection", icon: Siren },
    { href: "/cooling", label: "Cooling Intelligence", icon: Snowflake },
    { href: "/renewable", label: "Renewable Energy", icon: Sun },
    { href: "/optimization", label: "Optimization Engine", icon: Workflow },
    { href: "/recommendations", label: "AI Recommendations", icon: Sparkles },
  ] },
  { group: "Insight", items: [
    { href: "/sustainability", label: "Sustainability", icon: Leaf },
    { href: "/reports", label: "Reports & Exports", icon: FileText },
  ] },
  { group: "System", items: [
    { href: "/iot", label: "IoT Devices", icon: Cpu },
    { href: "/models", label: "Model Management", icon: BarChart3 },
    { href: "/users", label: "User Management", icon: Users, roles: ["super_admin"] },
    { href: "/settings", label: "System Configuration", icon: Settings },
  ] },
];
const ROLE: Record<string, string> = { super_admin: "Super Administrator", energy_manager: "Facilities / Energy Manager", zone_manager: "Zone Manager", viewer: "Viewer / Auditor" };

export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname(); const router = useRouter();
  const raw = useSyncExternalStore(() => () => {}, () => localStorage.getItem("gridwise_user") ?? "", () => null);
  const user: User | null = raw ? getUser() : null; const ready = !!user; const [open, setOpen] = useState(false);
  useEffect(() => { if (raw === "") router.replace("/login"); }, [raw, router]);
  const notes = useQuery({ queryKey: ["notes"], queryFn: () => api("/api/anomalies?status=open&days=3&limit=1"), enabled: ready });
  if (!user) return <div className="grid h-screen place-items-center text-sm text-ink2">Loading GRIDWISE AI…</div>;
  const logout = async () => { try { await api("/api/auth/logout", { method: "POST" }); } catch {} clearSession(); router.replace("/login"); };
  return (
    <div className="flex min-h-screen">
      <aside className={cx("fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-navy text-slate-300 transition-transform lg:translate-x-0", open ? "translate-x-0" : "-translate-x-full")}>
        <Link href="/dashboard" className="flex items-center gap-2.5 px-5 py-5 text-white"><span className="grid h-9 w-9 place-items-center rounded-xl bg-primary"><Zap className="h-5 w-5" /></span>
          <span><span className="block text-[15px] font-semibold leading-tight">GRIDWISE AI</span><span className="block text-[10px] uppercase tracking-widest text-slate-400">Monitor · Predict · Optimize</span></span></Link>
        <nav className="flex-1 overflow-y-auto px-3 pb-4" aria-label="Main navigation">
          {NAV.map((g) => (
            <div key={g.group} className="mb-3">
              <p className="px-3 py-1 text-[10px] font-semibold uppercase tracking-widest text-slate-500">{g.group}</p>
              {g.items.filter((i) => !i.roles || i.roles.includes(user.role)).map((i) => {
                const active = path === i.href || path.startsWith(i.href + "/");
                return <Link key={i.href} href={i.href} onClick={() => setOpen(false)} className={cx("flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition", active ? "bg-primary/20 text-white" : "hover:bg-navy2 hover:text-white")}><i.icon className="h-4 w-4" />{i.label}</Link>;
              })}
            </div>
          ))}
        </nav>
        <div className="border-t border-white/10 p-4 text-xs">
          <p className="font-medium text-white">{user.name}</p><p className="text-slate-400">{ROLE[user.role]}</p>
          <button onClick={logout} className="mt-3 flex items-center gap-1.5 text-slate-300 hover:text-white"><LogOut className="h-3.5 w-3.5" />Sign out</button>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-line bg-white/90 px-4 py-2.5 backdrop-blur lg:px-8">
          <div className="flex items-center gap-3">
            <button className="lg:hidden" onClick={() => setOpen(!open)} aria-label="Toggle menu"><Menu className="h-5 w-5" /></button>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-violet-100 px-3 py-1 text-xs font-medium text-violet-800" data-testid="sim-banner"><Activity className="h-3.5 w-3.5" />SIMULATED DEMONSTRATION DATA · not measured NIT Rourkela energy data</span>
          </div>
          <div className="flex items-center gap-3 text-xs text-ink2">
            <Link href="/anomalies" className="relative" aria-label="Open anomalies"><Bell className="h-5 w-5" />{notes.data?.total > 0 && <span className="absolute -right-1.5 -top-1.5 grid h-4 min-w-4 place-items-center rounded-full bg-bad px-1 text-[10px] font-semibold text-white">{notes.data.total}</span>}</Link>
            <span className="hidden sm:block">Times shown in IST</span>
          </div>
        </header>
        <main className="min-w-0 flex-1 px-4 py-6 lg:px-8">{children}</main>
        <footer className="px-8 py-4 text-[11px] text-muted">GRIDWISE AI operates in monitoring &amp; recommendation mode only. It does not control any electrical or HVAC equipment. Savings shown are estimates unless marked MEASURED.</footer>
      </div>
    </div>
  );
}
