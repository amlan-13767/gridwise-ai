"""Anomaly detection: seasonal robust z-score (same hour & day-type), rolling-mean ratio,
and Isolation Forest. Anomalies are investigation leads, NOT confirmed wastage."""
import json
import numpy as np, pandas as pd
from ml.common import load_readings, REPORTS


def severity(dev_pct):
    a = abs(dev_pct)
    return "critical" if a >= 100 else "high" if a >= 60 else "medium" if a >= 30 else "low"


def detect(df: pd.DataFrame, z_thr=4.0, contamination=0.004):
    from sklearn.ensemble import IsolationForest  # imported lazily: keeps the API process small
    d = df.copy(); d["ts"] = d.timestamp.dt.floor("h")
    h = d.groupby(["building_id", "zone_type", "ts"]).agg(
        y=("power_demand_kw", "mean"), label=("injected_anomaly", "max") if "injected_anomaly" in d else ("power_demand_kw", "size")).reset_index()
    loc = h.ts + pd.Timedelta(hours=5, minutes=30)
    h["hour"] = loc.dt.hour; h["daytype"] = (loc.dt.dayofweek >= 5).astype(int)
    grp = h.groupby(["building_id", "hour", "daytype"]).y
    h["expected"] = grp.transform("median")
    h["mad"] = grp.transform(lambda s: np.median(np.abs(s - s.median())) * 1.4826)
    h["mad"] = np.maximum(h.mad, 0.03 * h.expected)  # floor
    h["z"] = (h.y - h.expected) / h.mad
    h["roll"] = h.groupby("building_id").y.transform(lambda s: s.shift(1).rolling(24, min_periods=6).mean())
    h["roll_ratio"] = h.y / h.roll
    h["ratio"] = h.y / h.expected
    # Isolation Forest per zone on [ratio, z, hour]
    h["iso"] = False
    for z, g in h.groupby("zone_type"):
        X = g[["ratio", "z", "hour"]].fillna(0)
        m = IsolationForest(n_estimators=150, contamination=contamination, random_state=42).fit(X)
        h.loc[g.index, "iso"] = m.predict(X) == -1
    stat = (h.z > z_thr) & (h.ratio > 1.25)
    sudden = (h.roll_ratio > 1.8) & (h.ratio > 1.3)
    iso = h.iso & (h.ratio > 1.2)
    h["flag"] = stat | sudden | iso
    h["method"] = np.select([stat, sudden, iso],
                            ["seasonal_robust_zscore", "rolling_mean_jump", "isolation_forest"], "")
    a = h[h.flag].copy()
    a["deviation_pct"] = (a.y / a.expected - 1) * 100
    a["severity"] = a.deviation_pct.map(severity)
    a["overnight"] = a.hour.between(0, 4)
    return h, a


def run_detection_report(df=None):
    df = load_readings() if df is None else df
    h, a = detect(df)
    rep = dict(total_flags=int(len(a)), method_counts=a.method.value_counts().to_dict())
    if "label" in h and h.label.max() <= 1:
        tp = int((h.flag & (h.label == 1)).sum()); fp = int((h.flag & (h.label == 0)).sum())
        fn = int((~h.flag & (h.label == 1)).sum())
        rep.update(precision=tp / max(tp + fp, 1), recall=tp / max(tp + fn, 1), tp=tp, fp=fp, fn=fn,
                   note="Evaluated against injected SIMULATED anomalies only (hourly granularity).")
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "anomaly_evaluation.json").write_text(json.dumps(rep, indent=2))
    print("anomalies", rep)
    return rep
