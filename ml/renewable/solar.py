"""Solar forecasting (SIMULATED generation). Baseline = hour-of-day mean; RF; XGBoost."""
import json, datetime as dt
import numpy as np, pandas as pd, joblib
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from ml.common import load_readings, metrics, MODELS, REPORTS

FEATURES = ["irradiance", "cloud_cover", "temperature", "hour", "doy", "capacity_kw"]
CAPACITY_KW = 400.0  # simulated installed capacity


def solar_hourly(df):
    d = df.copy(); d["ts"] = d.timestamp.dt.floor("h")
    s = d.groupby(["ts", "building_id"]).agg(g=("solar_generation_kw", "mean")).reset_index()
    tot = s.groupby("ts").g.sum().rename("y")
    w = d.groupby("ts").agg(irradiance=("irradiance", "mean"), cloud_cover=("cloud_cover", "mean"),
                            temperature=("temperature", "mean"))
    out = pd.concat([tot, w], axis=1).reset_index()
    loc = out.ts + pd.Timedelta(hours=5, minutes=30)
    out["hour"] = loc.dt.hour; out["doy"] = loc.dt.dayofyear; out["capacity_kw"] = CAPACITY_KW
    return out


def train_solar(df=None, version="v1"):
    df = load_readings() if df is None else df
    s = solar_hourly(df); n = len(s)
    tr, va, te = s.iloc[:int(n * .67)], s.iloc[int(n * .67):int(n * .84)], s.iloc[int(n * .84):]
    base = tr.groupby("hour").y.mean()
    res = {"baseline_hourly_average": metrics(te.y, te.hour.map(base))}
    models = {"random_forest": RandomForestRegressor(n_estimators=80, max_depth=12, min_samples_leaf=4, n_jobs=-1, random_state=42),
              "xgboost": XGBRegressor(n_estimators=300, max_depth=5, learning_rate=.06, random_state=42)}
    fitted = {}
    for k, m in models.items():
        m.fit(tr[FEATURES], tr.y); res[k] = metrics(te.y, m.predict(te[FEATURES]))
        res[k]["val"] = metrics(va.y, m.predict(va[FEATURES]))
        res[k]["resid_std"] = float(np.std(va.y - m.predict(va[FEATURES]))); fitted[k] = m
    best = min(fitted, key=lambda k: res[k]["val"]["rmse"]); res["selected_by_validation_rmse"] = best
    joblib.dump(dict(model=fitted[best], features=FEATURES, resid_std=res[best]["resid_std"],
                     version=f"solar-{best}-{version}"), MODELS / "solar.joblib")
    rep = dict(version=version, trained_at=dt.datetime.now(dt.timezone.utc).isoformat(),
               dataset="SIMULATED solar generation", metrics=res,
               note="Forecast inputs (irradiance/cloud) are assumed to come from a weather forecast service.")
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "solar_evaluation.json").write_text(json.dumps(rep, indent=2))
    print("solar", best, {k: round(v["rmse"], 2) for k, v in res.items() if isinstance(v, dict) and "rmse" in v})
    return rep
