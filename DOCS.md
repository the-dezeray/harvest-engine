Comp-322      Adne-Documentation 
1                  DataFarmers              
Adaptive Network Engine - AdNe 
PROJECT PROPOSAL 
AI-Enhanced Real-Time Campus Network Traffic Monitor 
Team Name: DataFarmers 
1. Team Members & Assigned Roles 
# Member Role Primary Responsibility 
1 Nadiah S Majafe Project Manager / Scrum 
Master 
Sprint coordination, GitHub project board, documentation, 
risk tracking 
2 Maatla Tlhalerwa AI/ML Engineer Load-prediction model (Prophet/LSTM), prediction REST API 
endpoint 
3 Desiree Chingwaru Backend Lead 
(Orchestrator) 
Auto-scaling controller, worker lifecycle management via 
Docker API 
4 Mary Abygail 
Santos Data Ingestion Lead Telemetry emitter scripts, RabbitMQ configuration, ingestion 
API (FastAPI) 
5 Barati Phologane Processing Worker Lead Worker pool logic, analytical rule engine, fault-tolerance 
mechanisms 
6 Patience Sandy Frontend & Visualization 
Lead 
Next.js dashboard, campus SVG map, real-time charts, 
scenario controls 
7 Omaatla Lekwapa QA & Testing Lead Integration tests, failure injection, performance benchmarks, 
demo preparation 
 
2. High-Level System Architecture 
The system follows a distributed pipeline architecture with built-in fault tolerance and proactive notification. Telemetry 
emitters simulate BIUST campus network access points and stream JSON payloads into a FastAPI ingestion service that 
validates and filters incoming data before forwarding to a RabbitMQ message broker which acts as a buffer between data 
ingestion and processing.  
A pool of distributed Python workers consumes the stream and evaluates analytical rules (such as detecting abnormal 
traffic spikes or access point failures). If a worker fails/dies, the RabbitMQ automatically redelivers or reassigns 
unacknowledged messages to healthy workers. It can even queue them again until they are assigned to a worker.  
We included an AI/ML service to monitor the platform’s operational metrics based on historical and real-time data and 
provide the scaling recommendations to an orchestrator that manages all worker containers via the Docker API and is 
responsible for the running of continuous heartbeat checks to detect and replace dead workers.  
A Gmail notification service delivers email alerts to IT technicians on ground for critical network incidents and the scaling 
of events.  
Results flow into Redis (real-time cache) and TimescaleDB (historical storage). Both feeding the Next.js dashboard 
deployed on Vercel to be viewed or displayed for anyone who has access to the dashboard. 
“The goal is to build a system that alerts the tech team in real-time and auto-scales our processing power to handle the 
load. Basically, we want to stop the "WiFi is down" complaints by making the campus network smart enough to heal itself 
before we even notice a lag.” 
 
 
 
 
 
Comp-322      Adne-Documentation 
2                  DataFarmers              
3. Technology Stack & Justification 
Layer Technology Justification 
Frontend Next.js + React (Vercel) 
Support SSR, which we use for fast initial loads and provide a React ecosystem 
for D3.js and Recharts; Vercel provides zero-config deployment with 
WebSocket support. 
Ingestion API Python (FastAPI) 
Handles many concurrent requests through the Async-native endpoints; native 
compatibility with AI/ML ecosystem; provides automatic OpenAPI 
documentation. 
Message Broker RabbitMQ 
Has a built-in message acknowledgment for fault tolerance; requeues all 
unpacked messages when a worker fails; topic-based routing; simpler than 
Kafka at our scale. 
Processing Python Workers 
Shares the same languages as AI/ML service, allowing direct use of NumPy 
and SciPy libraries for data processing. Also works well inside Docker 
containers using multiprocessing. 
Orchestrator FastAPI + Docker API 
Allows programmatic container lifecycle management and heartbeat monitoring 
detection which allows for the replacement of failed workers; REST interface for 
dashboard health queries. 
AI/ML Service Prophet / LSTM Prophet for quick time-series forecasting; LSTM as stretch goal; served as 
REST endpoint. 
Notifications Gmail API (SMTP) 
Email alerts for critical network incidents to on-ground IT staff. Extends 
monitoring beyond the dashboard for offline awareness. BIUST staff already 
use Gmail, requiring no additional setup on recipient side. 
Cache Redis Sub-millisecond reads; pub/sub for real-time dashboard updates; TTL-based 
rolling aggregates.  
Database PostgreSQL + 
TimescaleDB 
Time-series optimized hypertables; support continuous aggregates; familiar 
SQL interface. 
Containers Docker 
Isolated components; orchestrator manages workers directly; reproducible 
environments. Allowing components to run smoother regardless of host 
machine. 
 
 
 
 
 
 
 
