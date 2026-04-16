import pika
import json

connection = pika.BlockingConnection(
    pika.ConnectionParameters('localhost')
)
channel = connection.channel()

channel.queue_declare(queue='traffic_queue')

messages = [
    {"traffic": 50},
    {"traffic": 120},
    {"traffic": 200},
    {"traffic": 80}
]

for msg in messages:
    channel.basic_publish(
        exchange='',
        routing_key='traffic_queue',
        body=json.dumps(msg)
    )
    print("Sent:", msg)

connection.close()