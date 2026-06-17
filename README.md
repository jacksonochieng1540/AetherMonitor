# AetherMonitor

An AI-Powered Infrastructure Monitoring Dashboard using Django, Celery, Channels, Redis, PostgreSQL, and scikit-learn.

## Application's Features 

- **Dynamic Agent Registration**: Ingests CPU, memory, disk, and network stats from multiple container or host agents.
- **Asynchronous Ingestion Pipeline**: API requests return immediately while Celery workers handle database operations, ML scoring, and alert generation.
- **ML Anomaly Detection**: Evaluates incoming telemetry points using an Isolation Forest model to detect system aberrations in real-time.
- **Real-time WebSockets Streaming**: Pushes live metrics updates and alert cards to the dashboard immediately.
- **Premium Glassmorphic UI**: Beautiful dark-theme dashboard with interactive charting, live logging console, and alert management controls.
- **Self-contained Docker Environment**: Orchestrated DB, Redis, Web, and Celery layers in a single compose configuration.

## Project Structure

```
├── docker-compose.yml
├── README.md
├── .github/
│   └── workflows/
│       └── ci.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── manage.py
│   ├── monitoring_project/   # Django project settings
│   ├── metrics/              # Ingestion API, WebSocket consumers, Celery tasks
│   ├── ml_engine/            # IsolationForest ML model
│   └── templates/
│       └── dashboard.html    # Glassmorphism HTML/CSS/JS frontend
└── agent/
    ├── requirements.txt
    └── agent.py              # Telemetry collection agent
```

## Running the Application

For a complete setup guide and verification logs, check [walkthrough.md](file:///home/notouriousmma/.gemini/antigravity/brain/0a33e3d6-4068-42e3-bc07-6a6122d8c6e6/walkthrough.md).

### 1. Start Server Stack
```bash
docker compose up --build
```
Access dashboard: `http://localhost:8000/`

### 2. Start Agent Client
```bash
cd agent
pip install -r requirements.txt
python agent.py --simulate-spikes
```
