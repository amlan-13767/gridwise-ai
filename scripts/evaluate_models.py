"""Print the saved evaluation reports (produced by scripts/train_models.py)."""
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from ml.common import REPORTS
for f in ("forecast_evaluation", "solar_evaluation", "anomaly_evaluation"):
    p = REPORTS / f"{f}.json"
    print(f"== {f}"); print(json.dumps(json.loads(p.read_text()), indent=1)[:4000] if p.exists() else "missing - run train_models.py")
