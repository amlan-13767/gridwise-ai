"""Reproducible SIMULATED 15-minute campus dataset. data_source is always 'simulated'."""
import numpy as np
import pandas as pd
from pathlib import Path
from .campus import build_campus

START = "2026-08-15"
DAYS = 90
SOLAR_KWP = 400.0
HOLIDAYS = {"2026-08-15", "2026-09-05", "2026-10-02", "2026-10-20", "2026-11-01"}  # demo list
SCHED = {"ACD-03": (8, 22.5), "ACD-05": (5.5, 20)}  # deliberately inefficient cooling schedules (simulated)
TARIFF_PEAK, TARIFF_OFF = 8.5, 6.0  # INR/kWh, assumption


def _profile(zone, btype, h, weekend, holiday):
    """Return load multiplier (0..~1.6) for fractional hour h."""
    g = lambda mu, s: np.exp(-0.5 * ((h - mu) / s) ** 2)
    off = weekend | holiday
    if zone == "Academic":
        work = (h >= 8.5) & (h <= 17.5)
        base = 0.25 + 0.75 * work * np.where(off, 0.35, 1.0)
        if btype == "library":
            base = 0.3 + 0.7 * ((h >= 8) & (h <= 22)) * np.where(off, .6, 1) + .2 * g(20, 1.5)
        if btype == "server_room":
            base = np.full_like(h, 0.9)
        if btype == "computer_lab":
            base = base + 0.15 * g(15, 2) * ~off
        return base
    if zone == "Hostel":
        return 0.35 + 0.35 * g(19.5, 2.2) + 0.2 * g(7.5, 1.2) + 0.2 * g(13, 1.2) + 0.1 * g(21.5, 1.5) * 1.0 + 0.0 * off
    return 0.4 + 0.5 * g(19.5, 2.0) + 0.25 * g(7, 1.3) + 0.1 * g(13, 2)


def generate(seed: int = 42, days: int = DAYS):
    rng = np.random.default_rng(seed)
    campus = build_campus(seed)
    idx = pd.date_range(START, periods=days * 96, freq="15min", tz="UTC")
    ist = idx + pd.Timedelta(hours=5, minutes=30)  # local time for behaviour
    h = (ist.hour + ist.minute / 60).to_numpy().astype(float)
    dow = ist.dayofweek.to_numpy()
    weekend = dow >= 5
    holiday = np.array([d.strftime("%Y-%m-%d") in HOLIDAYS for d in ist])
    doy = ist.dayofyear.to_numpy()
    # weather (Odisha-like, simulated)
    seas = 29 + 3 * np.sin(2 * np.pi * (doy - 150) / 365 * -1)
    temp = seas - 4 + 8 * np.exp(-0.5 * ((h - 14) / 3.5) ** 2) + rng.normal(0, .6, len(idx))
    # smooth cloud AR(1)
    cloud = np.zeros(len(idx)); c = .4
    for i in range(len(idx)):
        c = .98 * c + .02 * rng.uniform(0, 1) + rng.normal(0, .02)
        cloud[i] = min(max(c, 0), 1)
    hum = np.clip(75 - 1.5 * (temp - 25) + 10 * cloud + rng.normal(0, 3, len(idx)), 30, 98)
    sun = np.clip(np.sin(np.pi * (h - 6) / 12), 0, None)
    irr = 1000 * sun * (1 - .75 * cloud)
    solar_total = SOLAR_KWP * (irr / 1000) * (1 - .004 * np.clip(temp - 25, 0, None)) * rng.normal(1, .02, len(idx))
    solar_total = np.clip(solar_total, 0, None)
    tariff = np.where((h >= 18) & (h < 22), TARIFF_PEAK, TARIFF_OFF)
    rows = []
    n_solar_b = [b["building_id"] for b in campus if b["zone_type"] == "Academic"][:4]
    for k, b in enumerate(campus):
        prof = _profile(b["zone_type"], b["building_type"], h, weekend, holiday)
        occ_frac = np.clip(prof if b["zone_type"] != "Hostel" else .7 + .2 * (h >= 22) + .1 * (h < 8), 0, 1)
        if b["zone_type"] == "Academic":
            occ_frac = ((h >= 9) & (h <= 17)) * np.where(weekend | holiday, .05, 1) * rng.uniform(.5, 1, len(idx))
        occ = np.round(occ_frac * b["capacity"] * (0.9 if b["zone_type"] != "Academic" else .6)).astype(int)
        cool_need = np.clip((temp - 24) / 10, 0, 1.2)
        s0, s1 = SCHED.get(b["building_id"], (8, 18))
        cool_sched = np.where(b["zone_type"] == "Academic", ((h >= s0) & (h <= s1)) * np.where(weekend | holiday, 0.15 if b["building_id"] not in SCHED else 1.0, 1.0), 1.0)
        cooling = b["base_kw"] * b["hvac_share"] * 2.2 * cool_need * np.where(
            b["zone_type"] == "Academic", cool_sched, .5 + .5 * (prof / prof.max()))
        power = b["base_kw"] * prof * (1 - b["hvac_share"]) + cooling
        power *= rng.normal(1, .04, len(idx))
        indoor = np.where(cooling > 0.2 * b['base_kw'] * b['hvac_share'], 24.2 + rng.normal(0, .5, len(idx)), 0.5 * temp + 12.5 + rng.normal(0, .4, len(idx)))
        mess = np.zeros(len(idx))
        if b["zone_type"] == "Hostel":
            pump = 6 * (((h >= 5) & (h < 7)) | ((h >= 17) & (h < 18.5)))
            power = power + pump
        label = np.zeros(len(idx), dtype=int)
        # inject anomalies (~0.4% of points + overnight events)
        for _ in range(rng.integers(2, 5)):
            s = rng.integers(0, len(idx) - 40)
            kind = rng.choice(["overnight", "spike", "step"])
            if kind == "overnight":
                night = np.where((h[s:s + 400] >= 0) & (h[s:s + 400] < 5))[0]
                if len(night) > 12:
                    sel = s + night[:16]
                    power[sel] += b["base_kw"] * rng.uniform(.6, 1.1); label[sel] = 1
            elif kind == "spike":
                power[s:s + 3] *= rng.uniform(1.8, 2.6); label[s:s + 3] = 1
            else:
                power[s:s + 24] *= rng.uniform(1.4, 1.8); label[s:s + 24] = 1
        # deterministic demo anomalies near the end of the window (local time)
        ldate = ist.strftime("%Y-%m-%d").to_numpy(); last = sorted(set(ldate))[-3:]
        if b["building_id"] == "HST-02":
            m = (ldate == last[0]) & (h >= 1) & (h < 4.5); power[m] += b["base_kw"] * .9; label[m] = 1
        if b["building_id"] == "ACD-01":
            m = (ldate == last[1]) & (h >= 0.5) & (h < 4); power[m] += b["base_kw"] * 1.0; label[m] = 1
        if b["building_id"] == "RES-03":
            m = (ldate == last[2]) & (h >= 19) & (h < 20.5); power[m] *= 2.2; label[m] = 1
        power = np.clip(power, .5, None)
        v = rng.normal(230, 2.5, len(idx)); cur = power * 1000 / (v * 1.732 * .9)
        df = pd.DataFrame(dict(
            timestamp=idx, building_id=b["building_id"], zone_type=b["zone_type"],
            meter_id=f"MTR-{b['building_id']}", energy_consumption_kwh=power * .25,
            power_demand_kw=power, voltage=v, current=cur, temperature=temp, humidity=hum,
            occupancy=occ, cooling_load_kw=cooling, indoor_temperature=indoor,
            solar_generation_kw=(solar_total * (.25 if b["building_id"] in n_solar_b else 0)),
            wind_generation_kw=0.0, electricity_tariff=tariff,
            is_holiday=holiday.astype(int), is_weekend=weekend.astype(int),
            cloud_cover=cloud, irradiance=irr, injected_anomaly=label, data_source="simulated"))
        rows.append(df)
    out = pd.concat(rows, ignore_index=True)
    return campus, out


def main(out_dir="data/synthetic"):
    campus, df = generate()
    p = Path(out_dir); p.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(campus).to_csv(p / "buildings.csv", index=False)
    df.to_parquet(p / "readings.parquet", index=False) if False else df.to_csv(p / "readings.csv.gz", index=False, float_format="%.4f")
    print(f"wrote {len(df):,} rows, {df.building_id.nunique()} buildings -> {p}")


if __name__ == "__main__":
    main()
