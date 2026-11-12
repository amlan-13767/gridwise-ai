import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from ml.forecasting.train import train_all
from ml.renewable.solar import train_solar
from ml.anomaly_detection.detect import run_detection_report
train_all(); train_solar(); run_detection_report()
