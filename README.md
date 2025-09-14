# Contract Analyzer (CrewAI, Ollama-only)

This project uses CrewAI to run a multi-agent analysis over a contract PDF located in `contracts/`.

Agents:
- Contract Purpose Analyst
- Commercial Clauses Analyst
- Legal Risk Assessor
- Mitigation Strategist
- Exploitative Contract Detector (sends alert email if exploitative)

## Setup (Ollama-only)

1. Install Ollama and ensure the daemon is running (defaults to http://127.0.0.1:11434).
2. Pull the model once:

```
ollama pull gemma3:1b
```

3. Create and activate a Python 3.10+ environment.
4. Install dependencies.
5. (Optional) Create a `.env` file only if you need email alerts:

```
# Email alerts (optional)
ALERT_TO_EMAIL=alerts@example.com
ALERT_FROM_EMAIL=notifier@example.com
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=notifier@example.com
SMTP_PASSWORD=your_smtp_password
SMTP_USE_TLS=true
```

Put your PDF in `contracts/` as `Master-Services-Agreement.pdf` (or edit `src/main.py`). No cloud API keys are required.

## Run

Use Python to run the CLI:

```
py -3 -m src.main
```

The output report is saved to `reports/<contract>_analysis.json` and an email is sent if the contract is flagged as exploitative.

## Backend API (FastAPI)

- Endpoints:
	- POST /analyze — multipart PDF upload; returns JSON with sections plus report path.
	- POST /chat — JSON { contract_text, analysis, question } -> { answer }.

Start the API (Windows / PowerShell):

```
py -3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

## Frontend (React + Vite)

1. In `frontend/`, install deps and start dev server:
```
npm install
npm run dev
```
2. If backend runs on a different host/port, create `frontend/.env` with:
```
VITE_API_URL=http://localhost:8000
```

Upload a PDF, view the plain-language summary and sections, then ask questions via chat.
