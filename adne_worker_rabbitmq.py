"""
AdNe - Processing Worker (Real RabbitMQ version)
Team: DataFarmers | Role: Processing Worker Lead
-------------------------------------------------
Prerequisites:
  pip install pika redis
  docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

Run ONE worker:
  python adne_worker_rabbitmq.py --id 1

Run THREE workers in separate terminals:
  python adne_worker_rabbitmq.py --id 1
  python adne_worker_rabbitmq.py --id 2
  python adne_worker_rabbitmq.py --id 3

Then run the test emitter (in another terminal):
  python adne_worker_rabbitmq.py --emit
"""

import argparse
import json
import time
import random
import logging
from datetime import datetime

import pika

# ─── Config ──────────────────────────────────────────────────────────────────
RABBITMQ_HOST  = "localhost"
QUEUE_NAME     = "adne.telemetry"      # Workers consume from this queue
RESULTS_QUEUE  = "adne.results"        # Workers publish results here
PREFETCH_COUNT = 1                     # Each worker handles 1 msg at a time (fair dispatch)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Worker %(name)s] %(message)s",
    datefmt="%H:%M:%S"
)


# ─── Rule Engine (same logic as demo, easily extended) ───────────────────────
def run_rules(msg: dict) -> dict | None:
    ap_id   = msg["access_point"]
    traffic = msg["traffic_mbps"]
    status  = msg["status"]

    if traffic > 80:
        return {"type": "TRAFFIC_SPIKE",  "ap": ap_id, "value": traffic,
                "message": f"High traffic on {ap_id}: {traffic} Mbps"}

    if status == "DOWN":
        return {"type": "AP_FAILURE",     "ap": ap_id, "value": 0,
                "message": f"Access point {ap_id} is DOWN"}

    if msg.get("latency_ms", 0) > 200:
        return {"type": "HIGH_LATENCY",   "ap": ap_id, "value": msg["latency_ms"],
                "message": f"High latency on {ap_id}: {msg['latency_ms']} ms"}

    return None


# ─── Worker ──────────────────────────────────────────────────────────────────
class NetworkWorker:
    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.log = logging.getLogger(str(worker_id))
        self.processed = 0
        self.alerts    = 0

    def connect(self):
        """Create a connection and channel to RabbitMQ."""
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST)
        )
        channel = connection.channel()

        # Declare queues (safe to call even if they already exist)
        channel.queue_declare(queue=QUEUE_NAME,   durable=True)
        channel.queue_declare(queue=RESULTS_QUEUE, durable=True)

        # Fair dispatch: don't give this worker a 2nd message until it acks the 1st
        channel.basic_qos(prefetch_count=PREFETCH_COUNT)

        return connection, channel

    def start(self):
        self.log.info("🟢 Starting — connecting to RabbitMQ...")
        connection, channel = self.connect()

        channel.basic_consume(
            queue=QUEUE_NAME,
            on_message_callback=self._on_message
        )

        self.log.info(f"Listening on queue '{QUEUE_NAME}' — waiting for messages...")
        try:
            channel.start_consuming()
        except KeyboardInterrupt:
            channel.stop_consuming()
            connection.close()
            self.log.info(f"🔴 Stopped (processed={self.processed}, alerts={self.alerts})")

    def _on_message(self, channel, method, properties, body):
        """Called automatically each time a message arrives."""
        try:
            msg = json.loads(body)

            # Simulate processing time
            time.sleep(random.uniform(0.05, 0.15))

            alert = run_rules(msg)

            result = {
                "worker":    self.worker_id,
                "timestamp": datetime.utcnow().isoformat(),
                "ap":        msg["access_point"],
                "traffic":   msg["traffic_mbps"],
                "alert":     alert,
            }

            # Publish result to results queue (Patience's dashboard will read this)
            channel.basic_publish(
                exchange="",
                routing_key=RESULTS_QUEUE,
                body=json.dumps(result),
                properties=pika.BasicProperties(delivery_mode=2)  # persistent
            )

            # ACK — tell RabbitMQ this message was handled successfully
            channel.basic_ack(delivery_tag=method.delivery_tag)

            self.processed += 1
            if alert:
                self.alerts += 1
                self.log.info(f"🚨 ALERT [{alert['type']}]: {alert['message']}")
            else:
                self.log.info(f"✅ OK  AP={msg['access_point']}  "
                              f"{msg['traffic_mbps']} Mbps  seq={msg.get('seq','?')}")

        except Exception as e:
            self.log.error(f"❌ Error: {e} — sending NACK (message will be requeued)")
            # NACK with requeue=True → RabbitMQ sends to another worker (fault tolerance)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


# ─── Test Emitter (run with --emit to push fake messages) ────────────────────
def emit_test_messages(n: int = 30):
    """Pushes fake telemetry into the queue so you can test workers."""
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST)
    )
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    access_points = ["AP-LIB-01", "AP-CAFE-02", "AP-LAB-03", "AP-ADMIN-04", "AP-DORM-05"]
    print(f"📡 Emitting {n} telemetry messages to '{QUEUE_NAME}'...")

    for i in range(n):
        msg = {
            "seq":          i + 1,
            "access_point": random.choice(access_points),
            "traffic_mbps": round(random.uniform(5, 120), 1),
            "latency_ms":   random.choice([20, 40, 60, 150, 250, 300]),
            "status":       random.choices(["UP", "DOWN"], weights=[90, 10])[0],
            "timestamp":    datetime.utcnow().isoformat(),
        }
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE_NAME,
            body=json.dumps(msg),
            properties=pika.BasicProperties(delivery_mode=2)  # persistent
        )
        print(f"  Sent #{i+1}: AP={msg['access_point']}  {msg['traffic_mbps']} Mbps  status={msg['status']}")
        time.sleep(0.1)

    connection.close()
    print(f"\n✅ Done. Check your worker terminals to see them processing.")


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AdNe Processing Worker")
    parser.add_argument("--id",   type=int, default=1,    help="Worker ID (1, 2, 3...)")
    parser.add_argument("--emit", action="store_true",    help="Emit test messages instead of running a worker")
    parser.add_argument("--n",    type=int, default=30,   help="Number of test messages to emit")
    args = parser.parse_args()

    if args.emit:
        emit_test_messages(args.n)
    else:
        worker = NetworkWorker(args.id)
        worker.start()
