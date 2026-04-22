import json
import os
import time
import uuid
import threading
import httpx
import pika
import redis

QUEUE_NAME = os.getenv("QUEUE_NAME", "network-data")
RABBIT_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBIT_USER = os.getenv("RABBITMQ_USER", "nexus")
RABBIT_PASS = os.getenv("RABBITMQ_PASS", "nexuspass")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://ml-service:8001")

ALERTS_KEY = os.getenv("ALERTS_KEY", "alerts")
APS_SET_KEY = os.getenv("APS_SET_KEY", "aps")
BUILDING_COUNTS_KEY = os.getenv("BUILDING_COUNTS_KEY", "building_counts")
TOTAL_PROCESSED_KEY = os.getenv("TOTAL_PROCESSED_KEY", "total_processed")
ADNE_FREQ = os.getenv("ADNE_FREQ", "1_day")
LIVE_TO_TARGET_SCALE = float(os.getenv("LIVE_TO_TARGET_SCALE", "800"))

FREQ_TO_SECONDS = {
    "10_minutes": 10 * 60,
    "1_hour": 60 * 60,
    "1_day": 24 * 60 * 60,
}

def redis_client():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def push_alert(r, alert):
    r.lpush(ALERTS_KEY, json.dumps(alert))
    r.ltrim(ALERTS_KEY, 0, 99)


def _seconds_for_freq(freq: str | None) -> int:
    if not freq:
        return FREQ_TO_SECONDS[ADNE_FREQ] if ADNE_FREQ in FREQ_TO_SECONDS else FREQ_TO_SECONDS["1_day"]
    return FREQ_TO_SECONDS.get(freq, FREQ_TO_SECONDS.get(ADNE_FREQ, FREQ_TO_SECONDS["1_day"]))

def ml_anomaly_monitor(stop_event):
    """
    Orchestrator: Compares live traffic with ML forecast.
    """
    r = redis_client()
    print("[orchestrator] ML anomaly monitor started")
    
    while not stop_event.is_set():
        try:
            # 1. Get live system throughput (total processed in last 30s)
            # For simplicity, we check the total increment in the last interval
            total_now = int(r.get(TOTAL_PROCESSED_KEY) or 0)
            time.sleep(10)
            total_later = int(r.get(TOTAL_PROCESSED_KEY) or 0)
            live_rate = (total_later - total_now) / 10.0 # messages per second
            live_rate_scaled = live_rate * LIVE_TO_TARGET_SCALE

            # 2. Get forecast from ML service
            with httpx.Client() as client:
                res = client.get(f"{ML_SERVICE_URL}/predict?periods=1", timeout=5)
                payload = res.json()
                forecast = payload.get("forecast", [])
                if forecast:
                    freq = str(payload.get("meta", {}).get("freq", ADNE_FREQ))
                    seconds_per_bucket = _seconds_for_freq(freq)
                    pred = forecast[0]
                    upper = float(pred["yhat_upper"]) / float(seconds_per_bucket)
                    lower = float(pred["yhat_lower"]) / float(seconds_per_bucket)

                    print(
                        "[orchestrator] rates "
                        f"freq={freq} bucket_s={seconds_per_bucket} "
                        f"live_raw={live_rate:.2f} live_scaled={live_rate_scaled:.2f} "
                        f"lower={lower:.2f} upper={upper:.2f} scale={LIVE_TO_TARGET_SCALE:.2f}"
                    )
                    
                    # 3. Detect anomaly
                    if live_rate_scaled > upper * 1.2:
                        push_alert(r, {
                            "id": str(uuid.uuid4()),
                            "type": "PREDICTED_ANOMALY",
                            "severity": "warning",
                            "timestamp": time.time(),
                            "message": f"Traffic ({live_rate_scaled:.1f} scaled msg/s) exceeds ML upper bound ({upper:.1f})",
                        })
                    elif live_rate_scaled < lower * 0.8 and live_rate_scaled > 0.05:
                        push_alert(r, {
                            "id": str(uuid.uuid4()),
                            "type": "PREDICTED_ANOMALY",
                            "severity": "critical",
                            "timestamp": time.time(),
                            "message": f"Traffic ({live_rate_scaled:.1f} scaled msg/s) dropped below ML lower bound ({lower:.1f})",
                        })

        except Exception as e:
            print(f"[orchestrator] monitor warning: {e}")
            time.sleep(5)

def handle_message(r, message):
    payload = message.get("payload") or {}
    ap_id = payload.get("ap_id")
    building = payload.get("building", "unknown")
    if not ap_id: return

    pipe = r.pipeline()
    pipe.sadd(APS_SET_KEY, ap_id)
    pipe.hincrby(BUILDING_COUNTS_KEY, building, 1)
    pipe.incr(TOTAL_PROCESSED_KEY)
    pipe.execute()

def run_worker():
    r = redis_client()
    credentials = pika.PlainCredentials(RABBIT_USER, RABBIT_PASS)
    params = pika.ConnectionParameters(host=RABBIT_HOST, credentials=credentials)

    stop_event = threading.Event()
    threading.Thread(target=ml_anomaly_monitor, args=(stop_event,), daemon=True).start()

    while True:
        try:
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            
            def callback(ch, method, properties, body):
                try:
                    msg = json.loads(body.decode("utf-8"))
                    handle_message(r, msg)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
            print(f"[worker] consuming from {RABBIT_HOST}...")
            channel.start_consuming()
        except Exception as e:
            print(f"[worker] error: {e}, retrying...")
            time.sleep(5)

if __name__ == "__main__":
    run_worker()
