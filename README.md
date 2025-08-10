# Bet-Oracle Live MVP (rebuild)

This package contains a minimal Live-mode MVP for Bet-Oracle.

## Structure
- backend/: FastAPI backend (app.py) with endpoints:
  - /health, /odds, /predict, /ws
  - ingest loop polls odds provider if ODDS_API_KEY set, else uses demo data
- frontend/: simple static page that connects to backend over WebSocket and shows odds/signals
- docker-compose.yml for local dev

## Quick local run (no docker)
1. python3 -m venv venv
2. source venv/bin/activate
3. pip install -r requirements.txt
4. cd backend && uvicorn app:app --host 0.0.0.0 --port 8000
5. Open frontend/index.html in your browser, set backend URL to http://localhost:8000 and click Connect WS

## Docker local
1. docker-compose up --build
2. Open frontend/index.html and set backend URL to http://localhost:8000

## Deploy to Render
1. Push repo to GitHub
2. Create Render web service (Docker)
3. Use backend/Dockerfile and set ODDS_API_KEY in env
