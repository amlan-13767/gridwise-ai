# ML pipeline
1. `scripts/generate_data.py` → 302,400 SIMULATED 15-minute rows (seed 42). `scripts/validate_data.py` checks schema/ranges/labels.
2. `scripts/train_models.py` trains, evaluates and saves (`ml/models/*.joblib`, `ml/reports/*.json`).
   * **Demand**: hourly per-building target, horizons 1 h / 24 h / 7 d. Lags are always ≥ horizon (tests prove no leakage). Chronological split 67/17/16 % (no shuffling). Candidates: historical hourly-average baseline, Linear Regression, Random Forest, XGBoost, LightGBM. The model with the lowest **validation** RMSE is saved. 80 % intervals use validation residual σ.
   * **Solar**: baseline vs Random Forest vs XGBoost on simulated irradiance/cloud/temperature.
   * **Anomalies**: robust z-score vs comparable hours (same hour, weekday/weekend), rolling-mean jump, Isolation Forest per zone. (Local Outlier Factor was not implemented.)
3. Inference at runtime (`services/forecast_service.py`): future weather/occupancy = recent 7-day climatology (no live weather service).
4. New models stay `pending_review`; only a super admin can promote.

## Results (SIMULATED data, held-out test, pooled over buildings; kW)
| horizon | baseline RMSE | selected | RMSE | MAE (baseline → model) | note |
|---|---|---|---|---|---|
| 1 h | 2.70 | LightGBM | 1.62 | 1.40 → 0.77 | ≈40 % lower RMSE |
| 24 h | 2.70 | XGBoost | 2.15 | 1.40 → 0.82 | ≈21 % lower RMSE |
| 7 d | 2.69 | XGBoost | 2.79 | 1.38 → 0.92 | **RMSE 4 % worse**, MAE 33 % better (anomaly-driven tails) |
| solar | 11.98 | Random Forest | 1.60 | 6.0 → 0.86 | XGBoost 1.57 |
Anomaly detector vs injected labels: precision 96.1 %, recall 94.4 %. Exact numbers: `ml/reports/*.json` (regenerated on each training run; the table may drift by retraining).
These numbers describe the simulator, not any real campus.
