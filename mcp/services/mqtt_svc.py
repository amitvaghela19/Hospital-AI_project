from __future__ import annotations

import json
from typing import Any

from mcp.common import MQTT_BROKER, MQTT_PORT

# Demo / stretch: simulated hospital vitals via local Mosquitto broker.


def publish_vitals(patient_id: str, heart_rate: int, spo2: float) -> dict[str, Any]:
    topic = f"hospital/vitals/{patient_id}"
    payload = {"patient_id": patient_id, "heart_rate": heart_rate, "spo2": spo2}
    try:
        import paho.mqtt.publish as publish

        publish.single(
            topic,
            payload=json.dumps(payload),
            hostname=MQTT_BROKER,
            port=MQTT_PORT,
        )
        return {"status": "published", "topic": topic, "payload": payload}
    except Exception as e:
        return {"status": "error", "topic": topic, "error": str(e)}


def subscribe_latest(topic: str = "hospital/vitals/#", timeout: float = 2.0) -> dict[str, Any]:
    try:
        import paho.mqtt.client as mqtt

        messages: list[dict] = []

        def on_message(_client, _userdata, msg):
            messages.append({"topic": msg.topic, "payload": msg.payload.decode("utf-8", errors="replace")})

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_message = on_message
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.subscribe(topic)
        client.loop_start()
        import time

        time.sleep(timeout)
        client.loop_stop()
        client.disconnect()
        return {"topic": topic, "messages": messages}
    except Exception as e:
        return {"topic": topic, "error": str(e), "messages": []}
