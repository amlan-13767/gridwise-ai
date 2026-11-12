import Link from "next/link";
import { Activity, Building2, Cpu, Home, Leaf, Map, Snowflake, Sparkles, Sun, TrendingUp, Zap, ShieldCheck } from "lucide-react";

const FEATURES = [
  { icon: TrendingUp, t: "Demand forecasting", d: "Next-hour, 24-hour and 7-day forecasts compared against a historical baseline, with honest metrics." },
  { icon: Activity, t: "Anomaly detection", d: "Seasonal baselines, robust statistics and Isolation Forest flag unusual consumption as investigation leads." },
  { icon: Snowflake, t: "Cooling intelligence", d: "Find HVAC running outside occupancy and estimate the saving with a constrained optimiser." },
  { icon: Sun, t: "Renewable forecasting", d: "Solar forecasts, surplus/deficit and load-shifting suggestions (simulated generation)." },
  { icon: Sparkles, t: "Explainable recommendations", d: "Every suggestion shows evidence, confidence and whether a saving is estimated or measured." },
  { icon: Leaf, t: "Sustainability reporting", d: "Configurable emission factor and tariff; all carbon figures are labelled estimates." },
];
const ZONES = [
  { icon: Building2, n: "Academic Area", d: "Departments, labs, library, admin and common facilities.", c: "#2a78d6" },
  { icon: Home, n: "Hostel Area", d: "Hostels, mess, pumps and common areas, normalised per occupied bed.", c: "#eb6834" },
  { icon: Home, n: "Residential Area", d: "Quarters clusters and shared infrastructure - aggregate only, privacy first.", c: "#1baf7a" },
];

export default function Landing() {
  return (
    <div className="bg-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2"><span className="grid h-9 w-9 place-items-center rounded-xl bg-primary text-white"><Zap className="h-5 w-5" /></span><b className="text-lg">GRIDWISE AI</b></div>
        <Link href="/login" className="rounded-lg bg-navy px-4 py-2 text-sm font-medium text-white hover:bg-navy2">Sign in</Link>
      </header>
      <section className="bg-gradient-to-b from-navy to-navy2 text-white">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <p className="mb-4 inline-flex rounded-full bg-white/10 px-3 py-1 text-xs tracking-wide">Smart Campus Energy Intelligence · NIT Rourkela use case</p>
          <h1 className="max-w-3xl text-5xl font-semibold leading-[1.1] tracking-tight">Monitor. Predict. Optimize. <span className="text-sky-300">Save.</span></h1>
          <p className="mt-5 max-w-2xl text-lg text-slate-300">One command centre for Academic, Hostel and Residential electricity - forecasting demand, spotting anomalies, trimming cooling waste and planning around solar.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/login" className="rounded-lg bg-primary px-5 py-3 text-sm font-semibold hover:bg-blue-500" data-testid="cta-login">Open the platform</Link>
            <a href="#how" className="rounded-lg border border-white/25 px-5 py-3 text-sm font-semibold hover:bg-white/10">How it works</a>
          </div>
          <p className="mt-6 flex items-center gap-2 text-xs text-slate-400"><ShieldCheck className="h-4 w-4" />Demonstration runs on clearly labelled SIMULATED data. Monitoring and recommendations only - no equipment is ever controlled.</p>
        </div>
      </section>
      <section className="mx-auto max-w-6xl px-6 py-16">
        <h2 className="text-2xl font-semibold">Three zones, one platform</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">{ZONES.map((z) => <div key={z.n} className="rounded-2xl border border-line p-5"><span className="grid h-10 w-10 place-items-center rounded-xl text-white" style={{ background: z.c }}><z.icon className="h-5 w-5" /></span><h3 className="mt-4 font-semibold">{z.n}</h3><p className="mt-1 text-sm text-ink2">{z.d}</p></div>)}</div>
      </section>
      <section id="how" className="bg-bg py-16"><div className="mx-auto max-w-6xl px-6">
        <h2 className="text-2xl font-semibold">What it does</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">{FEATURES.map((f) => <div key={f.t} className="rounded-2xl bg-white p-5 shadow-sm"><f.icon className="h-5 w-5 text-primary" /><h3 className="mt-3 font-semibold">{f.t}</h3><p className="mt-1 text-sm text-ink2">{f.d}</p></div>)}</div>
      </div></section>
      <section className="mx-auto max-w-6xl px-6 py-14">
        <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900"><Cpu className="mt-0.5 h-5 w-5 shrink-0" />
          <div><b>Honest by design.</b> Sample buildings, meters, solar assets and map positions are simulated and do not represent the real NIT Rourkela inventory. Real meters connect through the same MQTT/HTTP ingestion pipeline once verified and authorised. Model accuracy shown is measured on simulated data only.</div></div>
      </section>
      <footer className="border-t border-line px-6 py-6 text-center text-xs text-muted"><Map className="mr-1 inline h-3.5 w-3.5" />GRIDWISE AI · open-source demonstration</footer>
    </div>
  );
}
