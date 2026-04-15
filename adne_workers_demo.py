"""
AdNe - Processing Worker Demo
Team: DataFarmers | Role: Processing Worker Lead
------------------------------------------------------
This demo simulates 3 workers consuming network telemetry
messages from a shared queue, running analytics rules,
and publishing results.

Run: python adne_workers_demo.py
"""

import threading
import queue
import time
import random
import json
from datetime import datetime


# ─── Simulated message queue (replace with RabbitMQ later) ───────────────────
message_queue = queue.Queue()
results = []
results_lock = threading.Lock()


# ─── Analytical Rule Engine ───────────────────────────────────────────────────
def run_rules(msg: dict) -> dict | None:
    """
    Evaluates analytical rules on a telemetry message.
    Returns an alert dict if a rule fires, otherwise None.
    """
    ap_id   = msg["access_point"]
    traffic = msg["traffic_mbps"]
    status  = msg["status"]

    # Rule 1: Traffic spike
    if traffic > 80:
        return {
            "type":    "TRAFFIC_SPIKE",
            "ap":      ap_id,
            "value":   traffic,
            "message": f"High traffic on {ap_id}: {traffic} Mbps"
        }

    # Rule 2: Access point down
    if status == "DOWN":
        return {
            "type":    "AP_FAILURE",
            "ap":      ap_id,
            "value":   0,
            "message": f"Access point {ap_id} is DOWN"
        }

    # Rule 3: Abnormal latency
    if msg.get("latency_ms", 0) > 200:
        return {
            "type":    "HIGH_LATENCY",
            "ap":      ap_id,
            "value":   msg["latency_ms"],
            "message": f"High latency on {ap_id}: {msg['latency_ms']} ms"
        }

    return None  # No alert; message processed normally


# ─── Worker ──────────────────────────────────────────────────────────────────
class NetworkWorker(threading.Thread):
    """
    A processing worker that:
    1. Consumes messages from the shared queue
    2. Runs the analytical rule engine
    3. Acknowledges (removes) the message on success
    4. Publishes results to the results store (Redis in production)
    """

    def __init__(self, worker_id: int, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.worker_id  = worker_id
        self.stop_event = stop_event
        self.processed  = 0
        self.alerts     = 0

    def run(self):
        print(f"[Worker {self.worker_id}] 🟢 Started")

        while not self.stop_event.is_set():
            try:
                # Block for up to 1 second waiting for a message
                msg = message_queue.get(timeout=1.0)
            except queue.Empty:
                continue  # No message yet; loop and check stop_event

            try:
                self._process(msg)
                message_queue.task_done()  # ← ACK (like RabbitMQ basic_ack)
                self.processed += 1

            except Exception as e:
                # In production: NACK → RabbitMQ requeues to another worker
                print(f"[Worker {self.worker_id}] ❌ Error processing msg: {e}")
                message_queue.task_done()

        print(f"[Worker {self.worker_id}] 🔴 Stopped "
              f"(processed={self.processed}, alerts={self.alerts})")

    def _process(self, msg: dict):
        # Simulate processing time (10–50 ms)
        time.sleep(random.uniform(0.01, 0.05))

        alert = run_rules(msg)

        result = {
            "worker":    self.worker_id,
            "timestamp": datetime.utcnow().isoformat(),
            "ap":        msg["access_point"],
            "traffic":   msg["traffic_mbps"],
            "alert":     alert,
        }

        # Publish result (in production: redis.publish("results", json.dumps(result)))
        with results_lock:
            results.append(result)

        if alert:
            self.alerts += 1
            print(f"  [Worker {self.worker_id}] 🚨 ALERT: {alert['message']}")
        else:
            print(f"  [Worker {self.worker_id}] ✅ OK   : AP={msg['access_point']} "
                  f"{msg['traffic_mbps']} Mbps  latency={msg.get('latency_ms',0)} ms")


# ─── Telemetry Emitter (simulates Mary's ingestion layer) ────────────────────
def emit_telemetry(n_messages: int = 20):
    """Generates fake campus network telemetry and puts it on the queue."""
    access_points = ["AP-LIB-01", "AP-CAFE-02", "AP-LAB-03",
                     "AP-ADMIN-04", "AP-DORM-05"]

    print(f"\n📡 Emitting {n_messages} telemetry messages...\n")
    for i in range(n_messages):
        msg = {
            "seq":          i + 1,
            "access_point": random.choice(access_points),
            "traffic_mbps": round(random.uniform(5, 120), 1),
            "latency_ms":   random.choice([20, 40, 60, 150, 250, 300]),
            "status":       random.choices(["UP", "DOWN"], weights=[90, 10])[0],
            "timestamp":    datetime.utcnow().isoformat(),
        }
        message_queue.put(msg)
        time.sleep(0.05)   # 50 ms between messages (simulates 20 msg/s stream)


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    NUM_WORKERS   = 3
    NUM_MESSAGES  = 20

    stop_event = threading.Event()

    # Spin up worker pool
    workers = [NetworkWorker(i + 1, stop_event) for i in range(NUM_WORKERS)]
    for w in workers:
        w.start()

    # Emit messages (in production this comes from FastAPI + RabbitMQ)
    emit_telemetry(NUM_MESSAGES)

    # Wait until every message has been processed
    message_queue.join()

    # Signal workers to stop
    stop_event.set()
    for w in workers:
        w.join()

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "─" * 50)
    print("📊  WORKER POOL SUMMARY")
    print("─" * 50)
    for w in workers:
        print(f"  Worker {w.worker_id}: processed={w.processed}  alerts={w.alerts}")

    all_alerts = [r for r in results if r["alert"]]
    print(f"\n  Total messages : {NUM_MESSAGES}")
    print(f"  Total alerts   : {len(all_alerts)}")
    print("─" * 50)

    if all_alerts:
        print("\n🚨  ALERT LOG:")
        for a in all_alerts:
            print(f"  [{a['timestamp']}] {a['alert']['type']} — {a['alert']['message']}")

    print("\n✅ Demo complete.\n")


if __name__ == "__main__":
    main()
