from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import uuid
import json
import os
import pika

app = FastAPI(title="Harvest Engine - Ingestion API")

# stores received messages for debugging
received_messages = []

# scenario state - emitters poll this every few seconds
scenario = {"mode": "normal"}

# rabbitmq connection settings (set by docker)
RABBIT_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBIT_USER = os.getenv("RABBITMQ_USER", "nexus")
RABBIT_PASS = os.getenv("RABBITMQ_PASS", "nexuspass")


# defines what shape the incoming data must be
class APReading(BaseModel):
    ap_id: str               # e.g. "LIB-AP-01"
    timestamp: float         # unix time
    connected_devices: int   # how many devices connected
    bandwidth_mbps: float    # bandwidth in use
    signal_strength_dbm: int # signal strength (negative number)
    packet_loss_pct: float   # packet loss percentage
    building: str            # e.g. "LIB", "ENG"


def send_to_queue(data: dict) -> dict:
    """
    wraps data in a message envelope and sends it to rabbitmq.
    falls back to memory if rabbitmq is unavailable.
    """
    message = {
        "id": str(uuid.uuid4()),
        "received_at": datetime.utcnow().isoformat(),
        "payload": data
    }

    try:
        credentials = pika.PlainCredentials(RABBIT_USER, RABBIT_PASS)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBIT_HOST, credentials=credentials)
        )
        channel = connection.channel()

        # create queue if it doesnt exist yet
        channel.queue_declare(queue="network-data", durable=True)

        # publish the message
        channel.basic_publish(
            exchange="",
            routing_key="network-data",
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)  # persistent
        )
        connection.close()
        print(f"[queue] {data['ap_id']} | {data['connected_devices']} devices | {data['building']}")

    except Exception as e:
        print(f"[warning] rabbitmq unavailable - storing in memory: {e}")

    return message


# health check
@app.get("/")
def home():
    return {
        "status": "running",
        "total_received": len(received_messages),
        "scenario": scenario["mode"],
        "timestamp": datetime.utcnow().isoformat()
    }


# main endpoint - emitter posts here every 2 seconds per AP
@app.post("/ingest")
def ingest(data: APReading):
    message = send_to_queue(data.model_dump())

    received_messages.append(message)
    if len(received_messages) > 300:
        received_messages.pop(0)

    return {
        "status": "received",
        "message_id": message["id"],
        "ap_id": data.ap_id
    }


# emitter checks this every 5 seconds to know what mode to run
@app.get("/scenario")
def get_scenario():
    return scenario


# dashboard or orchestrator calls this to change the mode
@app.post("/scenario")
def set_scenario(mode: str):
    valid_modes = ["normal", "spike", "cooldown", "failure"]
    if mode not in valid_modes:
        return {"error": f"valid modes are: {valid_modes}"}
    scenario["mode"] = mode
    print(f"[scenario] switched to {mode}")
    return {"mode": mode, "status": "updated"}


# shows recent messages - good for debugging
@app.get("/messages")
def get_messages():
    recent = list(reversed(received_messages[-20:]))
    return {"count": len(recent), "messages": recent}


# breakdown by building - dashboard uses this
@app.get("/status")
def status():
    by_building = {}
    for m in received_messages:
        b = m["payload"].get("building", "unknown")
        by_building[b] = by_building.get(b, 0) + 1

    return {
        "total_messages": len(received_messages),
        "by_building": by_building,
        "scenario": scenario["mode"]
    }
