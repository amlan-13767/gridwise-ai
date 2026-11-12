"""SIMULATED IoT publisher. Every message carries source='simulated'. Publishes via MQTT (default) or HTTP.
Usage: python iot/simulators/simulator.py --mode http --count 3  |  --mode mqtt --broker localhost"""
import argparse, json, sys, pathlib, time, random, datetime as dt, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from backend.app.core.config import settings
from backend.app.iot.ingest import device_key


def payload(meter, kw, ts):
    return dict(meter_id=meter, timestamp=ts.strftime("%Y-%m-%dT%H:%M:%SZ"), power_kw=round(kw, 2), energy_kwh=round(kw * 0.25, 3),
                voltage=round(random.gauss(230, 2), 1), current=round(kw * 1000 / (230 * 1.732 * .9), 1), source="simulated")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["mqtt", "http"], default="http")
    ap.add_argument("--api", default="http://localhost:8000"); ap.add_argument("--broker", default="localhost")
    ap.add_argument("--meters", nargs="+", default=["MTR-ACD-01", "MTR-HST-01"]); ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--interval", type=float, default=1.0); ap.add_argument("--duplicate", action="store_true")
    a = ap.parse_args()
    start = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
    if a.mode == "mqtt":
        import paho.mqtt.client as mqtt
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if settings.MQTT_USERNAME:
            c.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
        c.connect(a.broker, 1883); c.loop_start()
    for i in range(a.count):
        for m in a.meters:
            ts = start + dt.timedelta(minutes=15 * i)
            p = payload(m, random.uniform(20, 60), ts)
            for _ in range(2 if a.duplicate else 1):
                key = device_key(settings.SECRET_KEY, m)
                if a.mode == "mqtt":
                    c.publish(f"gridwise/campus/simulated/{m.lower()}", json.dumps(dict(p, device_key=key)))
                else:
                    r = urllib.request.Request(a.api + "/api/iot/ingest", json.dumps(p).encode(),
                                               {"Content-Type": "application/json", "X-Device-Key": key})
                    print(m, ts, urllib.request.urlopen(r).read().decode())
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
