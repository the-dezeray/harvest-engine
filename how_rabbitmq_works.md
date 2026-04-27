\# How RabbitMQ Works in AdNe



\## What is RabbitMQ

RabbitMQ is a message broker that acts as a middleman between the 

ingestion layer and the processing workers. It receives messages 

from Mary's ingestion API and queues them for my workers to consume.



\## Queues Used

\- adne.telemetry — workers consume from this queue

\- adne.results — workers publish results to this queue



\## How Messages Flow

1\. Mary's ingestion layer publishes telemetry to adne.telemetry

2\. RabbitMQ holds the message in the queue

3\. A worker picks it up and processes it

4\. Worker sends ACK to confirm it is done

5\. Result is published to adne.results for the dashboard



\## Fault Tolerance

\- If a worker crashes before sending ACK, RabbitMQ redelivers 

&#x20; the message to another worker automatically

\- If a worker cannot process a message it sends NACK and 

&#x20; RabbitMQ requeues it to another worker

\- No messages are lost even if workers fail



\## Why RabbitMQ

\- Built-in message acknowledgement for fault tolerance

\- Automatically requeues messages on worker failure

\- Simpler than Kafka at our scale

\- Supports multiple workers consuming from same queue

