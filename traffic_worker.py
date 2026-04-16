import pika
import json

THRESHOLD = 100

def callback(ch, method, properties, body):
    data = json.loads(body)
    traffic = data.get("traffic", 0)

    if traffic > THRESHOLD:
        print(f"[ALERT] High traffic: {traffic}")
    else:
        print(f"[OK] Traffic: {traffic}")

    ch.basic_ack(delivery_tag=method.delivery_tag)

connection = pika.BlockingConnection(
    pika.ConnectionParameters('localhost')
)
channel = connection.channel()

channel.queue_declare(queue='traffic_queue')

channel.basic_qos(prefetch_count=1)

channel.basic_consume(
    queue='traffic_queue',
    on_message_callback=callback
)

print("Waiting for messages...")
channel.start_consuming()