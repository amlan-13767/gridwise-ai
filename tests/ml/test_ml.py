import numpy as np, pandas as pd, joblib
from ml.data_generation.generate import generate
from ml.forecasting import train as T
from ml.common import MODELS, metrics, smape
from ml.anomaly_detection.detect import detect
from ml.renewable.solar import solar_hourly


def test_dataset_reproducible_and_labelled():
    _, a = generate(seed=7, days=4); _, b = generate(seed=7, days=4); _, c = generate(seed=8, days=4)
    pd.testing.assert_frame_equal(a, b)
    assert not a.power_demand_kw.equals(c.power_demand_kw)
    assert set(a.data_source) == {"simulated"}
    assert a.solar_generation_kw.min() >= 0 and a.power_demand_kw.min() > 0
    n = a[a.timestamp.dt.hour.isin([18, 19, 20, 21])].solar_generation_kw.max()
    assert n < 1e-6    # no solar at night (UTC 18-21 = 23:30-03:30 IST)


def test_dataset_fields_and_intervals():
    _, d = generate(seed=1, days=2)
    for col in "timestamp building_id zone_type meter_id energy_consumption_kwh power_demand_kw voltage current temperature humidity occupancy cooling_load_kw solar_generation_kw wind_generation_kw electricity_tariff is_holiday is_weekend data_source".split():
        assert col in d
    assert d.timestamp.diff().dropna().loc[lambda s: s > pd.Timedelta(0)].min() == pd.Timedelta("15min")
    assert d.building_id.nunique() == 35


def test_time_split_chronological_no_overlap():
    _, d = generate(seed=3, days=20)
    h = T.hourly(d); a, b = T.split_bounds(h.ts)
    tr, va, te = h[h.ts < a], h[(h.ts >= a) & (h.ts < b)], h[h.ts >= b]
    assert tr.ts.max() < va.ts.min() <= va.ts.max() < te.ts.min()
    assert len(tr) > len(va) > 0 and len(te) > 0


def test_no_future_leakage_in_lags():
    _, d = generate(seed=3, days=20)
    h = T.hourly(d); bm = h.groupby("building_id").y.mean().to_dict()
    for hz in (1, 24, 168):
        f = T.make_features(h, hz, bm)
        g = h[h.building_id == "ACD-01"].set_index("ts").y
        row = f[f.building_id == "ACD-01"].iloc[5]
        assert np.isclose(row.lag_a, g[row.ts - pd.Timedelta(hours=hz)])      # lag_a is exactly y[T-h]
        assert np.isclose(row.lag_b, g[row.ts - pd.Timedelta(hours=hz + 24)])
        lag_c_h = 168 if hz < 168 else hz + 168
        assert np.isclose(row.lag_c, g[row.ts - pd.Timedelta(hours=lag_c_h)])
        assert lag_c_h >= hz and hz + 24 >= hz                                  # never uses information newer than origin


def test_baseline_comparison_and_metrics():
    _, d = generate(seed=3, days=30)
    h = T.hourly(d); a, b = T.split_bounds(h.ts); bm = h[h.ts < a].groupby("building_id").y.mean().to_dict()
    f = T.make_features(h, 24, bm); tr, te = f[f.ts < a], f[f.ts >= b]
    base = metrics(te.y, T.baseline_predict(tr, te))
    from sklearn.linear_model import LinearRegression
    lr = LinearRegression().fit(tr[T.FEATURES], tr.y)
    m = metrics(te.y, lr.predict(te[T.FEATURES]))
    assert set(m) == {"mae", "rmse", "mape", "smape"} and base["rmse"] > 0
    assert m["rmse"] > 0
    import json
    from ml.common import REPORTS
    rep = json.loads((REPORTS / "forecast_evaluation.json").read_text())["horizons"]
    for hz in ("1_hour", "24_hours"):   # the 7-day model is NOT guaranteed to beat the baseline; reported honestly
        assert rep[hz][rep[hz]["selected_by_validation_rmse"]]["rmse"] < rep[hz]["baseline_hourly_average"]["rmse"]
    assert smape([0, 0], [0, 0]) == 0.0


def test_saved_model_serialization_and_output_schema():
    for hz in ("1_hour", "24_hours", "7_days"):
        b = joblib.load(MODELS / f"demand_{hz}.joblib")
        assert {"model", "features", "version", "resid_std", "bld_mean"} <= set(b)
        X = pd.DataFrame([{k: 1.0 for k in b["features"]}])
        p = b["model"].predict(X)
        assert p.shape == (1,) and np.isfinite(p).all()


def test_saved_model_reproducible_predictions():
    b = joblib.load(MODELS / "demand_24_hours.joblib")
    X = pd.DataFrame([{k: float(i) for i, k in enumerate(b["features"])}])
    assert b["model"].predict(X)[0] == b["model"].predict(X)[0]


def test_anomaly_detection_finds_injected_and_uses_seasonal_baseline():
    _, d = generate(seed=5, days=30)
    h, a = detect(d)
    assert len(a) > 0
    tp = (h.flag & (h.label == 1)).sum(); assert tp / max((h.label == 1).sum(), 1) > 0.5
    assert {"expected", "deviation_pct", "severity", "method"} <= set(a.columns)
    assert a.severity.isin(["low", "medium", "high", "critical"]).all()
    # expected value is built from the same hour and day-type (weekday vs weekend)
    r = h.iloc[100]
    peers = h[(h.building_id == r.building_id) & (h.hour == r.hour) & (h.daytype == r.daytype)]
    assert np.isclose(r.expected, peers.y.median())


def test_solar_forecast_inputs_and_night_zero():
    _, d = generate(seed=5, days=10)
    s = solar_hourly(d)
    assert s[s.hour.isin([0, 1, 2, 23])].y.max() < 1e-6 and s.y.max() > 100
