from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import uuid
import json
import os
import subprocess
import pika
import redis
import httpx

app = FastAPI(title="Harvest Engine - Ingestion API")

cors_origins_env = os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
)
allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# stores received messages for debugging
received_messages = []

# scenario state - emitters poll this every few seconds
scenario = {"mode": "normal"}

# rabbitmq connection settings (set by docker)
RABBIT_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBIT_USER = os.getenv("RABBITMQ_USER", "nexus")
RABBIT_PASS = os.getenv("RABBITMQ_PASS", "nexuspass")

# redis connection settings (set by docker)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://ml-service:8001")

REDIS_BUILDING_COUNTS_KEY = os.getenv("BUILDING_COUNTS_KEY", "building_counts")
REDIS_TOTAL_PROCESSED_KEY = os.getenv("TOTAL_PROCESSED_KEY", "total_processed")
REDIS_ALERTS_KEY = os.getenv("ALERTS_KEY", "alerts")
LIVE_TO_TARGET_SCALE = float(os.getenv("LIVE_TO_TARGET_SCALE", "800"))
WORKER_MAX_COUNT = int(os.getenv("WORKER_MAX_COUNT", "10"))
COMPOSE_FILE_PATH = os.getenv(
    "COMPOSE_FILE_PATH",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml")),
)

_redis_client = None


def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=2,
        )
    return _redis_client


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
    except Exception:
        pass

    return message


def _run_compose_command(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker-compose", "-f", COMPOSE_FILE_PATH, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _parse_worker_count(stdout: str) -> int:
    raw = stdout.strip()
    if not raw:
        return 0

    parsed: list[dict] = []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            parsed = [item for item in data if isinstance(item, dict)]
        elif isinstance(data, dict):
            parsed = [data]
    except json.JSONDecodeError:
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    parsed.append(item)
            except json.JSONDecodeError:
                continue

    count = 0
    for item in parsed:
        state = str(item.get("State", "")).lower()
        service = item.get("Service")
        if service == "worker" and state == "running":
            count += 1
    return count


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


@app.get("/workers")
def get_workers():
    try:
        ps_res = _run_compose_command(["ps", "worker", "--format", "json"])
        if ps_res.returncode != 0:
            return {
                "status": "error",
                "count": 0,
                "error": (ps_res.stderr or "failed to read worker state").strip(),
            }
        return {
            "status": "ok",
            "count": _parse_worker_count(ps_res.stdout),
            "max_count": WORKER_MAX_COUNT,
        }
    except Exception as ex:
        return {"status": "error", "count": 0, "error": str(ex)}


@app.post("/workers/scale")
def scale_workers(count: int):
    if count < 1:
        return {"status": "error", "error": "count must be >= 1"}
    if count > WORKER_MAX_COUNT:
        return {"status": "error", "error": f"count must be <= {WORKER_MAX_COUNT}"}

    try:
        scale_res = _run_compose_command(
            ["up", "-d", "--scale", f"worker={count}", "worker"],
            timeout=60,
        )
        if scale_res.returncode != 0:
            return {
                "status": "error",
                "error": (scale_res.stderr or "scale command failed").strip(),
            }

        ps_res = _run_compose_command(["ps", "worker", "--format", "json"])
        current_count = _parse_worker_count(ps_res.stdout) if ps_res.returncode == 0 else count
        return {"status": "scaled", "count": current_count, "requested_count": count}
    except Exception as ex:
        return {"status": "error", "error": str(ex)}


# shows recent/all messages - good for debugging
@app.get("/messages")
def get_messages(limit: int | None = None):
    if limit is not None and limit < 1:
        limit = 1
    if limit is not None and limit > 300:
        limit = 300

    recent = list(reversed(received_messages if limit is None else received_messages[-limit:]))
    return {"count": len(recent), "messages": recent}


@app.get("/forecast")
async def get_forecast(periods: int = 12):
    """Proxy to ML Service forecast"""
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(f"{ML_SERVICE_URL}/predict?periods={periods}", timeout=10)
            return res.json()
        except Exception as e:
            return {"error": f"ML service unreachable: {e}"}


@app.get("/ml-stats")
async def get_ml_stats():
    """Proxy to ML Service evaluate/health"""
    async with httpx.AsyncClient() as client:
        try:
            health = await client.get(f"{ML_SERVICE_URL}/health", timeout=5).then(lambda r: r.json())
            eval_res = await client.get(f"{ML_SERVICE_URL}/evaluate", timeout=30).then(lambda r: r.json())
            return {"health": health, "performance": eval_res}
        except Exception:
            # simple version if await chaining is complex
            try:
                h = await client.get(f"{ML_SERVICE_URL}/health")
                e = await client.get(f"{ML_SERVICE_URL}/evaluate")
                return {"health": h.json(), "performance": e.json()}
            except Exception as ex:
                return {"error": str(ex)}


@app.get("/alerts")
def get_alerts(limit: int | None = None):
    if limit is not None and limit < 1:
        limit = 1
    if limit is not None and limit > 200:
        limit = 200
    try:
        r = get_redis_client()
        # No limit means return the full live alert stream.
        raw = r.lrange(REDIS_ALERTS_KEY, 0, -1) if limit is None else r.lrange(REDIS_ALERTS_KEY, 0, limit - 1)
        alerts = [json.loads(item) for item in raw]
        return {"count": len(alerts), "alerts": alerts}
    except Exception:
        return {"count": 0, "alerts": []}


# breakdown by building - dashboard uses this
@app.get("/status")
def status():
    try:
        r = get_redis_client()
        total_processed = int(r.get(REDIS_TOTAL_PROCESSED_KEY) or 0)
        raw_counts = r.hgetall(REDIS_BUILDING_COUNTS_KEY) or {}
        by_building = {k: int(v) for k, v in raw_counts.items()}
        return {
            "total_processed": total_processed,
            "by_building": by_building,
            "scenario": scenario["mode"],
            "source": "redis",
            "live_to_target_scale": LIVE_TO_TARGET_SCALE,
        }
    except Exception:
        return {
            "total_processed": len(received_messages),
            "by_building": {},
            "scenario": "error",
            "source": "memory",
            "live_to_target_scale": LIVE_TO_TARGET_SCALE,
        }
