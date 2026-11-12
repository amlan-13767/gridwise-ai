"""Run saved models to produce forecasts. Lags are always >= horizon (no leakage); future weather &
occupancy use a climatology of the last 7 days (stand-in for a weather forecast service)."""
import datetime as dt, math
import joblib, numpy as np, pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from ml.common import MODELS
from ml.forecasting.constants import FEATURES, ZONES, HORIZONS
from ml.data_generation.generate import HOLIDAYS
from ml.renewable.constants import FEATURES as SFEAT
from ..models.tables import Forecast, Building, Zone
from . import common, model_service

IST = pd.Timedelta(hours=5, minutes=30)
_models: dict = {}


def load_model(name: str):
    """joblib bundles are loaded once per process (sklearn/xgboost are imported only when first needed)."""
    if name not in _models:
        _models[name] = joblib.load(MODELS / f"{name}.joblib")
    return _models[name]


def _climatology(db, origin, bmap):
    w = common.weather_frame(db, origin - dt.timedelta(days=7))
    w["h"] = (pd.to_datetime(w.timestamp) + IST).dt.hour
    wc = w.groupby("h")[["temperature", "humidity", "cloud_cover", "irradiance"]].mean()
    o = common.occupancy_frame(db, origin - dt.timedelta(days=7))
    o["h"] = (pd.to_datetime(o.timestamp) + IST).dt.hour
    oc = o.groupby(["building_id", "h"]).occupancy.mean()
    return wc, oc


def predict_building_frame(hist: pd.DataFrame, bundle, hz: int, steps, origin, wc, oc, bid, zone_type):
    """hist: hourly y for one building indexed by ts. Returns DataFrame ts, pred."""
    y = hist.set_index("ts").y
    rows = []
    for k in steps:
        T = origin + pd.Timedelta(hours=k)
        lc = 168 if hz < 168 else hz + 168
        try:
            la, lb, lcv = y[T - pd.Timedelta(hours=hz)], y[T - pd.Timedelta(hours=hz + 24)], y[T - pd.Timedelta(hours=lc)]
        except KeyError:
            continue
        loc = T + IST
        rows.append(dict(ts=T, lag_a=la, lag_b=lb, lag_c=lcv, hour=loc.hour, dow=loc.dayofweek, month=loc.month,
                         is_weekend=int(loc.dayofweek >= 5), is_holiday=int(loc.strftime("%Y-%m-%d") in HOLIDAYS),
                         temperature=wc.temperature.get(loc.hour, 28), humidity=wc.humidity.get(loc.hour, 70),
                         occupancy=oc.get((bid, loc.hour), 0), zone_code=ZONES[zone_type],
                         bld_mean=bundle["bld_mean"].get(bid_code(bid), y.mean())))
    return pd.DataFrame(rows)


_codes = {}


def bid_code(bid):
    return _codes.get(bid)


def run_forecast(db: Session, horizons=("1_hour", "24_hours", "7_days")):
    origin = pd.Timestamp(common.data_now(db)).floor("h")
    bmap = common.building_map(db)
    for bid, (b, zt) in bmap.items():
        _codes[bid] = b.code
    hf = common.hourly_frame(db, (origin - pd.Timedelta(days=16)).to_pydatetime())
    wc, oc = _climatology(db, origin.to_pydatetime(), bmap)
    gen = dt.datetime.utcnow()
    for hname in horizons:
        hz = HORIZONS[hname]
        bundle = load_model(f"demand_{hname}")
        steps = [1] if hz == 1 else list(range(1, 25)) if hz == 24 else list(range(1, 169))
        db.execute(delete(Forecast).where(Forecast.horizon == hname, Forecast.scope.in_(["building", "zone", "campus"])))
        agg = {}
        for bid, (b, zt) in bmap.items():
            g = hf[hf.building_id == bid]
            X = predict_building_frame(g, bundle, hz, steps, origin, wc, oc, bid, zt)
            if X.empty:
                continue
            p = np.clip(bundle["model"].predict(X[FEATURES]), 0, None)
            half = 1.2816 * bundle["resid_std"]
            for t, v in zip(X.ts, p):
                db.add(Forecast(building_id=bid, scope="building", zone_type=zt, forecast_timestamp=t.to_pydatetime(),
                                generated_at=gen, horizon=hname, predicted_demand_kw=float(v),
                                lower_bound_kw=float(max(0, v - half)), upper_bound_kw=float(v + half),
                                model_version=bundle["version"],
                                confidence_metadata=dict(interval="80% from validation residual std", half_width_kw=float(half),
                                                         inputs="lags>=horizon; climatology weather; SIMULATED training data")))
                for key in (("campus", None), ("zone", zt)):
                    a = agg.setdefault((key, t), [0.0, 0.0])
                    a[0] += float(v); a[1] += half ** 2
        for ((scope, zt), t), (v, h2) in agg.items():
            half = math.sqrt(h2)
            db.add(Forecast(building_id=None, scope=scope, zone_type=zt, forecast_timestamp=t.to_pydatetime(), generated_at=gen,
                            horizon=hname, predicted_demand_kw=v, lower_bound_kw=max(0, v - half), upper_bound_kw=v + half,
                            model_version=bundle["version"],
                            confidence_metadata=dict(interval="root-sum-square of building half-widths (assumes independent errors)")))
    model_service.touch_prediction(db, "demand_forecast")
    db.commit()


def solar_predict(db, origin, steps=range(1, 25)):
    bundle = load_model("solar")
    w = common.weather_frame(db, (origin - pd.Timedelta(days=7)).to_pydatetime())
    w["h"] = (pd.to_datetime(w.timestamp) + IST).dt.hour
    wc = w.groupby("h")[["temperature", "cloud_cover", "irradiance"]].mean()
    rows = []
    for k in steps:
        T = origin + pd.Timedelta(hours=k); loc = T + IST
        rows.append(dict(ts=T, irradiance=wc.irradiance.get(loc.hour, 0), cloud_cover=wc.cloud_cover.get(loc.hour, .4),
                         temperature=wc.temperature.get(loc.hour, 28), hour=loc.hour, doy=loc.dayofyear, capacity_kw=400.0))
    X = pd.DataFrame(rows)
    p = np.clip(bundle["model"].predict(X[SFEAT]), 0, None); half = 1.2816 * bundle["resid_std"]
    X["pred"] = p; X["lower"] = np.clip(p - half, 0, None); X["upper"] = p + half
    return X, bundle["version"]


def run_solar_forecast(db: Session):
    origin = pd.Timestamp(common.data_now(db)).floor("h")
    X, ver = solar_predict(db, origin)
    db.execute(delete(Forecast).where(Forecast.scope == "solar"))
    for r in X.itertuples():
        db.add(Forecast(building_id=None, scope="solar", zone_type=None, forecast_timestamp=r.ts.to_pydatetime(),
                        horizon="24_hours", predicted_demand_kw=float(r.pred), lower_bound_kw=float(r.lower),
                        upper_bound_kw=float(r.upper), model_version=ver,
                        confidence_metadata=dict(note="SIMULATED solar generation forecast (kW)")))
    model_service.touch_prediction(db, "solar_forecast")
    db.commit()
    return X
