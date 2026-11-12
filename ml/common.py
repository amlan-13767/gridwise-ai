import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "synthetic"
MODELS = ROOT / "ml" / "models"
REPORTS = ROOT / "ml" / "reports"


def load_readings(path=None) -> pd.DataFrame:
    df = pd.read_csv(path or DATA / "readings.csv.gz", parse_dates=["timestamp"])
    return df


def load_buildings() -> pd.DataFrame:
    return pd.read_csv(DATA / "buildings.csv")


def smape(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    d = (np.abs(y) + np.abs(p)) / 2
    return float(np.mean(np.where(d == 0, 0, np.abs(y - p) / np.where(d == 0, 1, d))) * 100)


def metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    nz = y != 0
    return dict(
        mae=float(np.mean(np.abs(y - p))),
        rmse=float(np.sqrt(np.mean((y - p) ** 2))),
        mape=float(np.mean(np.abs((y[nz] - p[nz]) / y[nz])) * 100) if nz.any() else None,
        smape=smape(y, p))
