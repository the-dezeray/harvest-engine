from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid
import json
import os
import pika

app = FastAPI(
    title="NexusFlow Ingestion API",
    description="Data ingestion layer for the NexusFlow analytics platform.",
    version="1.0.0"
)

# In-memory fallback store
message_store = []

# Read RabbitMQ config from environment variables
# os.getenv("VAR", "default") reads the variable, falls back to default if not set
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "nexus")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "nexuspass")


# ── Data Models ────────────────────────────────────────────────────────────
# These define what shape of data each endpoint accepts
# If someone sends the wrong fields, FastAPI automatically rejects it

class SensorPayload(BaseModel):
    device_id: str          # which device sent this e.g. "sensor-001"
    sensor_type: str        # what it measures e.g. "temperature"
    value: float            # the reading e.g. 36.7
    unit: str               # unit of measurement e.g. "celsius"
    location: Optional[str] = "unknown"  # optional, defaults to "unknown"

class SocialPayload(BaseModel):
    platform: str           # e.g. "twitter", "reddit"
    content: str            # the actual text
    author: Optional[str] = "anonymous"
    sentiment_hint: Optional[float] = None  # pre-computed sentiment if available

class FinancialPayload(BaseModel):
    ticker: str             # e.g. "BTC", "AAPL"
    price: float
    volume: Optional[int] = 0
    currency: str = "USD"


# ── RabbitMQ connection ────────────────────────────────────────────────────

def get_channel():
    """
    Opens a connection to RabbitMQ and returns a channel.
    Think of the connection as a phone call,
    and the channel as the conversation happening inside it.
    """
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
    )
    channel = connection.channel()

    # Declare the queue — creates it if it doesn't exist
    # durable=True means the queue survives a RabbitMQ restart
    channel.queue_declare(queue='data-stream', durable=True)

    return connection, channel


def publish(topic: str, data: dict) -> dict:
    """
    Wraps the data in a message envelope and sends it to RabbitMQ.
    If RabbitMQ isn't available, saves to memory so the API doesn't crash.
    """
    message = {
        "id": str(uuid.uuid4()),        # unique ID for this message
        "topic": topic,
        "timestamp": datetime.utcnow().isoformat(),
        "payload": data
    }

    try:
        connection, channel = get_channel()
        channel.basic_publish(
            exchange='',                        # default exchange
            routing_key='data-stream',          # which queue to send to
            body=json.dumps(message),           # convert dict to JSON string
            properties=pika.BasicProperties(
                delivery_mode=2                 # 2 = persistent, survives restart
            )
        )
        connection.close()
        print(f"[RabbitMQ] ✓ sent to {topic}")

    except Exception as e:
        # RabbitMQ not available — store in memory as fallback
        print(f"[WARNING] RabbitMQ unavailable, storing in memory: {e}")

    message_store.append(message)
    return message


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/")
def root():
    """Health check — tells you the API is alive."""
    return {
        "service": "NexusFlow Ingestion API",
        "status": "online",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/status")
def status():
    """
    Shows how many messages have come in per topic.
    The dashboard and orchestrator call this to monitor health.
    """
    topics = {}
    for m in message_store:
        t = m["topic"]
        topics[t] = topics.get(t, 0) + 1

    return {
        "status": "online",
        "total_messages": len(message_store),
        "by_topic": topics,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/ingest/sensor")
def ingest_sensor(data: SensorPayload):
    """
    Accepts IoT sensor readings.
    Clients POST here → message goes into RabbitMQ → workers process it.
    """
    message = publish("data-stream", {
        "type": "sensor",
        **data.model_dump()     # unpacks the model into a plain dict
    })
    return {
        "status": "accepted",
        "message_id": message["id"],
        "queued_at": message["timestamp"]
    }


@app.post("/ingest/social")
def ingest_social(data: SocialPayload):
    """
    Accepts social media feed items.
    Workers will run sentiment analysis on the content field.
    """
    message = publish("data-stream", {
        "type": "social",
        **data.model_dump()
    })
    return {
        "status": "accepted",
        "message_id": message["id"],
        "queued_at": message["timestamp"]
    }


@app.post("/ingest/financial")
def ingest_financial(data: FinancialPayload):
    """
    Accepts financial ticker updates.
    Workers will compute moving averages on the price field.
    """
    message = publish("data-stream", {
        "type": "financial",
        **data.model_dump()
    })
    return {
        "status": "accepted",
        "message_id": message["id"],
        "queued_at": message["timestamp"]
    }


@app.get("/messages")
def get_messages(limit: int = 20):
    """
    Returns the last N messages received.
    Use this to debug — confirms data is flowing in correctly.
    """
    recent = message_store[-limit:]
    return {
        "count": len(recent),
        "messages": list(reversed(recent))
    }


@app.delete("/messages")
def clear_messages():
    """Wipes the in-memory store. Useful for clean testing."""
    message_store.clear()
    return {"status": "cleared"}