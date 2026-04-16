import json
import os
import time
import uuid
import threading

import pika
import redis

QUEUE_NAME = os.getenv("QUEUE_NAME", "network-data")

RABBIT_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBIT_USER = os.getenv("RABBITMQ_USER", "nexus")
RABBIT_PASS = os.getenv("RABBITMQ_PASS", "nexuspass")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

SPIKE_THRESHOLD = int(os.getenv("SPIKE_THRESHOLD", "120"))
PACKET_LOSS_THRESHOLD = float(os.getenv("PACKET_LOSS_THRESHOLD", "10"))

OFFLINE_SECONDS = int(os.getenv("OFFLINE_SECONDS", "12"))
OFFLINE_CHECK_INTERVAL = int(os.getenv("OFFLINE_CHECK_INTERVAL", "5"))

ALERTS_KEY = os.getenv("ALERTS_KEY", "alerts")
APS_SET_KEY = os.getenv("APS_SET_KEY", "aps")
BUILDING_COUNTS_KEY = os.getenv("BUILDING_COUNTS_KEY", "building_counts")
TOTAL_PROCESSED_KEY = os.getenv("TOTAL_PROCESSED_KEY", "total_processed")


def redis_client() -> redis.Redis:
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def ap_key(ap_id: str, suffix: str) -> str:
    return f"ap:{ap_id}:{suffix}"


def push_alert(r: redis.Redis, alert: dict, max_len: int = 100) -> None:
    r.lpush(ALERTS_KEY, json.dumps(alert))
    r.ltrim(ALERTS_KEY, 0, max_len - 1)


def offline_monitor(stop_event: threading.Event) -> None:
    r = redis_client()

    while not stop_event.is_set():
        try:
            ap_ids = r.smembers(APS_SET_KEY)
            now = time.time()

            for ap_id in ap_ids:
                last_seen_raw = r.get(ap_key(ap_id, "last_seen"))
                status_key = ap_key(ap_id, "status")
                current_status = r.get(status_key) or "unknown"

                offline = False
                if last_seen_raw is None:
                    offline = True
                else:
                    try:
                        offline = (now - float(last_seen_raw)) > OFFLINE_SECONDS
                    except ValueError:
                        offline = True

                if offline and current_status != "offline":
                    r.set(status_key, "offline")
                    push_alert(
                        r,
                        {
                            "id": str(uuid.uuid4()),
                            "type": "ap_offline",
                            "severity": "critical",
                            "ap_id": ap_id,
                            "timestamp": now,
                            "message": f"{ap_id} appears offline (no data for {OFFLINE_SECONDS}s)",
                        },
                    )

        except Exception as e:
            print(f"[offline-monitor] warning: {e}")

        stop_event.wait(OFFLINE_CHECK_INTERVAL)


def handle_message(r: redis.Redis, message: dict) -> None:
    payload = message.get("payload") or {}

    ap_id = payload.get("ap_id")
    building = payload.get("building", "unknown")
    if not ap_id:
        raise ValueError("missing ap_id")

    now = time.time()

    # persist live state
    latest = {
        "ap_id": ap_id,
        "building": building,
        "timestamp": payload.get("timestamp"),
        "connected_devices": payload.get("connected_devices"),
        "bandwidth_mbps": payload.get("bandwidth_mbps"),
        "signal_strength_dbm": payload.get("signal_strength_dbm"),
        "packet_loss_pct": payload.get("packet_loss_pct"),
        "received_at": message.get("received_at"),
    }

    status_key = ap_key(ap_id, "status")
    previous_status = r.get(status_key) or "unknown"

    pipe = r.pipeline()
    pipe.sadd(APS_SET_KEY, ap_id)
    pipe.set(ap_key(ap_id, "latest"), json.dumps(latest))
    pipe.set(ap_key(ap_id, "last_seen"), str(now), ex=max(OFFLINE_SECONDS * 3, 30))
    pipe.set(status_key, "online")
    pipe.hincrby(BUILDING_COUNTS_KEY, building, 1)
    pipe.incr(TOTAL_PROCESSED_KEY)
    pipe.execute()

    # recovery alert
    if previous_status == "offline":
        push_alert(
            r,
            {
                "id": str(uuid.uuid4()),
                "type": "ap_recovered",
                "severity": "info",
                "ap_id": ap_id,
                "building": building,
                "timestamp": now,
                "message": f"{ap_id} is back online",
            },
        )

    # rule engine (minimum)
    connected = payload.get("connected_devices")
    packet_loss = payload.get("packet_loss_pct")

    if isinstance(connected, (int, float)) and connected >= SPIKE_THRESHOLD:
        push_alert(
            r,
            {
                "id": str(uuid.uuid4()),
                "type": "traffic_spike",
                "severity": "warning",
                "ap_id": ap_id,
                "building": building,
                "timestamp": now,
                "value": connected,
                "message": f"Traffic spike on {ap_id}: {connected} connected devices",
            },
        )

    if isinstance(packet_loss, (int, float)) and packet_loss >= PACKET_LOSS_THRESHOLD:
        push_alert(
            r,
            {
                "id": str(uuid.uuid4()),
                "type": "high_packet_loss",
                "severity": "warning",
                "ap_id": ap_id,
                "building": building,
                "timestamp": now,
                "value": packet_loss,
                "message": f"High packet loss on {ap_id}: {packet_loss}%",
            },
        )


def run_worker() -> None:
    r = redis_client()

    credentials = pika.PlainCredentials(RABBIT_USER, RABBIT_PASS)
    params = pika.ConnectionParameters(host=RABBIT_HOST, credentials=credentials)

    stop_event = threading.Event()
    monitor_thread = threading.Thread(target=offline_monitor, args=(stop_event,), daemon=True)
    monitor_thread.start()

    while True:
        try:
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.basic_qos(prefetch_count=1)

            def callback(ch, method, properties, body):
                try:
                    msg = json.loads(body.decode("utf-8"))
                    handle_message(r, msg)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    print(f"[worker] error: {e}")
                    # requeue so another worker can retry
                    try:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                    except Exception:
                        pass

            print(f"[worker] consuming {QUEUE_NAME} from {RABBIT_HOST} ...")
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback, auto_ack=False)
            channel.start_consuming()

        except Exception as e:
            print(f"[worker] connection error: {e} (retrying in 3s)")
            time.sleep(3)


if __name__ == "__main__":
    run_worker()
