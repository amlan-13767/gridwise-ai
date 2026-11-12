"""Demand forecasting: baseline vs LinearRegression / RandomForest / XGBoost / LightGBM.
Time-ordered split (no shuffling). Lags are always >= horizon, so no future leakage."""
import json, datetime as dt
import numpy as np, pandas as pd, joblib
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from ml.common import load_readings, load_buildings, metrics, MODELS, REPORTS

HORIZONS = {"1_hour": 1, "24_hours": 24, "7_days": 168}
SEED = 42
FEATURES = ["lag_a", "lag_b", "lag_c", "hour", "dow", "month", "is_weekend", "is_holiday",
            "temperature", "humidity", "occupancy", "zone_code", "bld_mean"]
ZONES = {"Academic": 0, "Hostel": 1, "Residential": 2}


def hourly(df):
    d = df.copy(); d["ts"] = d.timestamp.dt.floor("h")
    g = d.groupby(["building_id", "zone_type", "ts"]).agg(
        y=("power_demand_kw", "mean"), temperature=("temperature", "mean"),
        humidity=("humidity", "mean"), occupancy=("occupancy", "mean"),
        is_holiday=("is_holiday", "max")).reset_index()
    return g.sort_values(["building_id", "ts"]).reset_index(drop=True)


def split_bounds(ts, train=.67, val=.17):
    u = np.sort(ts.unique()); a = u[int(len(u) * train)]; b = u[int(len(u) * (train + val))]
    return a, b


def make_features(h, horizon, bld_mean):
    """Row for target time T uses y[T-horizon] (last known at forecast origin) and older."""
    out = []
    for b, g in h.groupby("building_id", sort=False):
        g = g.copy()
        g["lag_a"] = g.y.shift(horizon)
        g["lag_b"] = g.y.shift(horizon + 24)
        g["lag_c"] = g.y.shift(168 if horizon <= 168 and horizon < 168 else horizon + 168)
        out.append(g)
    f = pd.concat(out)
    local = f.ts + pd.Timedelta(hours=5, minutes=30)
    f["hour"] = local.dt.hour; f["dow"] = local.dt.dayofweek; f["month"] = local.dt.month
    f["is_weekend"] = (f.dow >= 5).astype(int)
    f["zone_code"] = f.zone_type.map(ZONES)
    f["bld_mean"] = f.building_id.map(bld_mean)
    return f.dropna(subset=["lag_a", "lag_b", "lag_c"]).reset_index(drop=True)


def baseline_predict(train, test):
    key = lambda d: (d.building_id, d.hour, d.is_weekend)
    m = train.groupby(["building_id", "hour", "is_weekend"]).y.mean().rename("p")
    return test.join(m, on=["building_id", "hour", "is_weekend"]).p.fillna(train.y.mean()).values


def candidates():
    return {
        "linear_regression": LinearRegression(),
        "random_forest": RandomForestRegressor(n_estimators=120, max_depth=14, min_samples_leaf=3, n_jobs=-1, random_state=SEED),
        "xgboost": XGBRegressor(n_estimators=400, max_depth=6, learning_rate=.06, subsample=.9, colsample_bytree=.9, random_state=SEED, n_jobs=-1),
        "lightgbm": LGBMRegressor(n_estimators=400, num_leaves=48, learning_rate=.06, random_state=SEED, verbose=-1, n_jobs=-1),
    }


def train_all(df=None, version="v1"):
    df = load_readings() if df is None else df
    h = hourly(df)
    a, b = split_bounds(h.ts)
    tr_raw = h[h.ts < a]
    bld_mean = tr_raw.groupby("building_id").y.mean().to_dict()
    MODELS.mkdir(parents=True, exist_ok=True); REPORTS.mkdir(parents=True, exist_ok=True)
    report = dict(version=version, trained_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                  dataset="data/synthetic/readings.csv.gz (SIMULATED)", seed=SEED, features=FEATURES,
                  split=dict(train_end=str(a), val_end=str(b), method="chronological, no shuffle"),
                  note="Metrics are on SIMULATED data and do not reflect real campus accuracy.",
                  horizons={})
    for name, hz in HORIZONS.items():
        f = make_features(h, hz, bld_mean)
        tr, va, te = f[f.ts < a], f[(f.ts >= a) & (f.ts < b)], f[f.ts >= b]
        res = {"baseline_hourly_average": metrics(te.y, baseline_predict(tr, te))}
        res["baseline_hourly_average"]["val"] = metrics(va.y, baseline_predict(tr, va))
        fitted = {}
        for mn, m in candidates().items():
            m.fit(tr[FEATURES], tr.y)
            res[mn] = metrics(te.y, m.predict(te[FEATURES]))
            res[mn]["val"] = metrics(va.y, m.predict(va[FEATURES]))
            res[mn]["resid_std"] = float(np.std(va.y - m.predict(va[FEATURES])))
            fitted[mn] = m
        best = min(fitted, key=lambda k: res[k]["val"]["rmse"])
        res["selected_by_validation_rmse"] = best
        res["improvement_vs_baseline_rmse_pct"] = float(
            (1 - res[best]["rmse"] / res["baseline_hourly_average"]["rmse"]) * 100)
        joblib.dump(dict(model=fitted[best], name=best, horizon=hz, features=FEATURES,
                         bld_mean=bld_mean, resid_std=res[best]["resid_std"], version=f"{best}-{version}"),
                    MODELS / f"demand_{name}.joblib")
        report["horizons"][name] = res
        print(name, best, {k: round(v["rmse"], 2) for k, v in res.items() if isinstance(v, dict) and "rmse" in v})
    (REPORTS / "forecast_evaluation.json").write_text(json.dumps(report, indent=2))
    return report
