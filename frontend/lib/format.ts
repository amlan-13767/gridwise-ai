export const n0 = (v: number | null | undefined) => v == null ? "-" : Math.round(v).toLocaleString("en-IN");
export const n1 = (v: number | null | undefined) => v == null ? "-" : v.toLocaleString("en-IN", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
export const n2 = (v: number | null | undefined) => v == null ? "-" : v.toLocaleString("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
export const inr = (v: number | null | undefined) => v == null ? "-" : "₹" + Math.round(v).toLocaleString("en-IN");
export const compact = (v: number | null | undefined) => v == null ? "-" : v >= 1e6 ? (v / 1e6).toFixed(2) + " M" : v >= 1e4 ? (v / 1e3).toFixed(1) + " k" : n0(v);
export const ist = (iso: string, o: Intl.DateTimeFormatOptions = { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false }) =>
  new Intl.DateTimeFormat("en-IN", { ...o, timeZone: "Asia/Kolkata" }).format(new Date(iso));
export const istHour = (iso: string) => ist(iso, { hour: "2-digit", minute: "2-digit", hour12: false });
export const istDay = (iso: string) => ist(iso, { day: "2-digit", month: "short" });
export const hh = (h: number) => `${String(h).padStart(2, "0")}:00`;
export const ZONE_COLOR: Record<string, string> = { Academic: "#2a78d6", Hostel: "#eb6834", Residential: "#1baf7a", Campus: "#0b1730" };
export const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
