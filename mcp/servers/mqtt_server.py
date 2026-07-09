from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp.services import mqtt_svc

mcp = FastMCP("hospital-mqtt")


@mcp.tool()
def publish_vitals(patient_id: str, heart_rate: int, spo2: float) -> str:
    """Publish simulated vitals to hospital/vitals/{patient_id} (demo IoT)."""
    return str(mqtt_svc.publish_vitals(patient_id, heart_rate, spo2))


@mcp.tool()
def subscribe_vitals(topic: str = "hospital/vitals/#", timeout: float = 2.0) -> str:
    """Subscribe briefly to vitals topics on local Mosquitto."""
    return str(mqtt_svc.subscribe_latest(topic, timeout))


if __name__ == "__main__":
    mcp.run()
