"""MQTT subscriber: gridwise/campus/<zone>/<building>/<meter> -> ingest(). Run as a separate worker process."""
import json, os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
import paho.mqtt.client as mqtt
from urllib.parse import urlparse
from backend.app.core.config import settings
from backend.app.core.db import SessionLocal
from backend.app.iot.ingest import ingest

TOPIC = "gridwise/campus/#"


def on_message(client, userdata, msg):
    try:
        body = json.loads(msg.payload.decode())
        key = body.pop("device_key", None)
    except Exception:
        print("rejected: not JSON", msg.topic); return
    with SessionLocal() as db:
        print(msg.topic, ingest(db, body, key, settings.SECRET_KEY))


def main():
    u = urlparse(settings.MQTT_BROKER_URL)
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if settings.MQTT_USERNAME:
        c.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
    c.on_connect = lambda cl, ud, f, rc, p=None: cl.subscribe(TOPIC)
    c.on_message = on_message
    c.connect(u.hostname or "localhost", u.port or 1883)
    c.loop_forever()


if __name__ == "__main__":
    main()
