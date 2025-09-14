from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.main import run_analysis, save_report, maybe_send_alert, _resolve_ollama_model  # type: ignore
from src.utils.pdf_loader import load_pdf_text  # type: ignore

app = FastAPI(title="Contract Analyzer API")
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()

REPORTS_DIR = Path("reports")
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# Expose reports directory
app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")


class AnalyzeResponse(BaseModel):
    report_json_path: str
    report_file: str
    report_url: str
    exploitative: Optional[bool] = None
    rationale: Optional[str] = None
    # Echo key sections to power the UI
    contract_text: str
    purpose: str
    commercial: str
    legal_risks: str
    mitigations: str
    alert: str
    plain: str
@app.get("/health")
def health():
    return {"status": "ok"}



@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_contract(file: UploadFile = File(...)):
    # Save uploaded file
    contents = await file.read()
    pdf_path = UPLOADS_DIR / file.filename
    with pdf_path.open("wb") as f:
        f.write(contents)

    # Enforce local Ollama model and run analysis
    model = _resolve_ollama_model()
    result = run_analysis(pdf_path, model=model)
    out_path = save_report(result, REPORTS_DIR, pdf_path.stem)
    name = out_path.name
    url = f"/reports/{name}"

    # Parse alert
    exploitative = None
    rationale = None
    try:
        data = json.loads(result.alert)
        exploitative = bool(data.get("exploitative"))
        rationale = data.get("rationale")
    except Exception:
        pass

    # Optional email alert
    maybe_send_alert(result.alert, pdf_path.name)

    return AnalyzeResponse(
        report_json_path=str(out_path),
        report_file=name,
        report_url=url,
        exploitative=exploitative,
        rationale=rationale,
        contract_text=load_pdf_text(pdf_path),
        purpose=result.purpose,
        commercial=result.commercial,
        legal_risks=result.legal_risks,
        mitigations=result.mitigations,
        alert=result.alert,
        plain=result.plain,
    )


class ChatRequest(BaseModel):
    contract_text: str
    analysis: str
    question: str


@app.post("/chat")
async def chat(req: ChatRequest):
    # Lightweight: just return 400 if missing values
    if not (req.contract_text and req.analysis and req.question):
        return {"error": "contract_text, analysis, and question are required"}

    from crewai import Crew, Process
    from src.agents.contract_agents import make_chat_agent
    from src.tasks.contract_tasks import chat_task

    # Use Ollama model for chat agent as well
    from crewai import LLM  # type: ignore
    model = _resolve_ollama_model()
    agent = make_chat_agent(LLM(model=model))
    task = chat_task(agent, req.contract_text, req.analysis, req.question)

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    _ = crew.kickoff()
    try:
        answer = task.output.raw if hasattr(task, "output") else ""
    except Exception:
        answer = ""

    return {"answer": answer}
