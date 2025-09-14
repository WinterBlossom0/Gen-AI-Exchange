from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, BackgroundTasks
import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.main import run_analysis, run_analysis_iter, save_report, maybe_send_alert, _resolve_ollama_model, AnalysisResult  # type: ignore
from src.utils.json_sanitizer import extract_json_object, extract_json_array  # type: ignore
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

# Suppress noisy access logs for status polling
class _SkipStatusFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        return "/analyze/status" not in msg

logging.getLogger("uvicorn.access").addFilter(_SkipStatusFilter())

load_dotenv()

REPORTS_DIR = Path("reports")
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# Expose reports directory
app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")

# In-memory job store for simple progress tracking
JOBS: Dict[str, Dict[str, Any]] = {}


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
    # Parsed fields for cleaner UI when possible
    commercial_parsed: Optional[dict] = None
    legal_risks_parsed: Optional[list] = None
    mitigations_parsed: Optional[list] = None
    alert_parsed: Optional[dict] = None
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

    # Parse and lightly post-process outputs for UI
    exploitative = None
    rationale = None
    commercial_parsed = None
    legal_risks_parsed = None
    mitigations_parsed = None
    alert_parsed = None
    # Robust parsing using sanitizer (handles extra text around JSON)
    obj = extract_json_object(result.commercial)
    commercial_parsed = obj if obj else None

    risks = extract_json_array(result.legal_risks)[:8]
    legal_risks_parsed = risks if risks else None

    mits = extract_json_array(result.mitigations)[:8]
    mitigations_parsed = mits if mits else None

    al = extract_json_object(result.alert)
    if al:
        alert_parsed = al
        exploitative = bool(al.get("exploitative"))
        rationale = al.get("rationale")
    else:
        alert_parsed = None

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
        commercial_parsed=commercial_parsed,
        legal_risks_parsed=legal_risks_parsed,
        mitigations_parsed=mitigations_parsed,
        alert_parsed=alert_parsed,
    )


class AnalyzeStartResponse(BaseModel):
    job_id: str


class AnalyzeStatusResponse(BaseModel):
    job_id: str
    status: str  # pending|running|done|error
    step: int
    total_steps: int
    message: Optional[str] = None
    current_agent: Optional[str] = None
    current_label: Optional[str] = None
    result: Optional[AnalyzeResponse] = None
    # Partials as tasks complete
    partials: Optional[Dict[str, Any]] = None


def _run_job(job_id: str, pdf_path: Path):
    try:
        JOBS[job_id]["status"] = "running"
        JOBS[job_id]["step"] = 0
        JOBS[job_id]["message"] = "Starting"
        JOBS[job_id]["outputs"] = {}
        model = _resolve_ollama_model()

        # Make full contract text available to the frontend immediately
        try:
            full_text = load_pdf_text(pdf_path)
            JOBS[job_id]["outputs"] = {**(JOBS[job_id].get("outputs") or {}), "contract_text": full_text}
        except Exception:
            pass

        outputs: Dict[str, Any] = {}
        steps = [
            ("Contract Purpose Analyst", "purpose"),
            ("Commercial Clauses Analyst", "commercial"),
            ("Legal Risk Assessor", "legal_risks"),
            ("Mitigation Strategist", "mitigations"),
            ("Exploitative Contract Detector", "alert"),
            ("Plain-Language Simplifier", "plain"),
        ]
        total = len(steps) + 1  # +1 for saving report
        JOBS[job_id]["total_steps"] = total

        # Iterate tasks sequentially and update status
        def _on_partial(part_label: str, data: Dict[str, Any]):
            cur = JOBS[job_id].get("outputs") or {}
            cur.update(data)
            JOBS[job_id]["outputs"] = cur

        for idx, (label, out) in enumerate(run_analysis_iter(pdf_path, model=model, on_partial=_on_partial), start=1):
            if JOBS.get(job_id, {}).get("cancelled"):
                JOBS[job_id]["message"] = "Cancelled"
                JOBS[job_id]["status"] = "cancelled"
                return
            # Find friendly agent name
            agent_name = next((name for name, lab in steps if lab == label), label)
            JOBS[job_id]["step"] = idx
            JOBS[job_id]["message"] = "Running"
            JOBS[job_id]["current_agent"] = agent_name
            JOBS[job_id]["current_label"] = label
            outputs[label] = out
            # Update partials for frontend
            part: Dict[str, Any] = {label: out}
            # Try parsed fields
            if label == "commercial":
                obj = extract_json_object(out)
                if obj:
                    part["commercial_parsed"] = obj
            elif label == "legal_risks":
                arr = extract_json_array(out)
                if arr:
                    part["legal_risks_parsed"] = arr[:8]
            elif label == "mitigations":
                arr = extract_json_array(out)
                if arr:
                    part["mitigations_parsed"] = arr[:8]
            elif label == "alert":
                al = extract_json_object(out)
                if al:
                    part["alert_parsed"] = al
            # merge into job outputs
            if not JOBS.get(job_id, {}).get("cancelled"):
                cur = JOBS[job_id].get("outputs") or {}
                cur.update(part)
                JOBS[job_id]["outputs"] = cur

        if JOBS.get(job_id, {}).get("cancelled"):
            JOBS[job_id]["message"] = "Cancelled"
            JOBS[job_id]["status"] = "cancelled"
            return
        JOBS[job_id]["step"] = total
        JOBS[job_id]["message"] = "Saving report"
        analysis_result = AnalysisResult(
            purpose=str(outputs.get("purpose", "")),
            commercial=str(outputs.get("commercial", "")),
            legal_risks=str(outputs.get("legal_risks", "")),
            mitigations=str(outputs.get("mitigations", "")),
            alert=str(outputs.get("alert", "")),
            plain=str(outputs.get("plain", "")),
        )
        out_path = save_report(analysis_result, REPORTS_DIR, pdf_path.stem)
        name = out_path.name
        url = f"/reports/{name}"

        # Parse fields like in /analyze
        exploitative = None
        rationale = None
        commercial_parsed = None
        legal_risks_parsed = None
        mitigations_parsed = None
        alert_parsed = None
        obj = extract_json_object(analysis_result.commercial)
        commercial_parsed = obj if obj else None

        risks = extract_json_array(analysis_result.legal_risks)[:8]
        legal_risks_parsed = risks if risks else None

        mits = extract_json_array(analysis_result.mitigations)[:8]
        mitigations_parsed = mits if mits else None

        al = extract_json_object(analysis_result.alert)
        if al:
            alert_parsed = al
            exploitative = bool(al.get("exploitative"))
            rationale = al.get("rationale")

        # Reconstruct a result-like object from outputs
        JOBS[job_id]["result"] = AnalyzeResponse(
            report_json_path=str(out_path),
            report_file=name,
            report_url=url,
            exploitative=exploitative,
            rationale=rationale,
            contract_text=load_pdf_text(pdf_path),
            purpose=analysis_result.purpose,
            commercial=analysis_result.commercial,
            legal_risks=analysis_result.legal_risks,
            mitigations=analysis_result.mitigations,
            alert=analysis_result.alert,
            plain=analysis_result.plain,
            commercial_parsed=commercial_parsed,
            legal_risks_parsed=legal_risks_parsed,
            mitigations_parsed=mitigations_parsed,
            alert_parsed=alert_parsed,
        )
        JOBS[job_id]["step"] = total
        JOBS[job_id]["message"] = "Done"
        JOBS[job_id]["status"] = "done"
    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["message"] = str(e)


@app.post("/analyze/start", response_model=AnalyzeStartResponse)
async def analyze_start(background: BackgroundTasks, file: UploadFile = File(...)):
    contents = await file.read()
    pdf_path = UPLOADS_DIR / file.filename
    with pdf_path.open("wb") as f:
        f.write(contents)

    job_id = os.urandom(8).hex()
    # Set total_steps to the real count (+1 for saving)
    total_steps = 6 + 1
    JOBS[job_id] = {
        "status": "pending",
        "step": 0,
        "total_steps": total_steps,
        "message": None,
        "current_agent": None,
        "current_label": None,
        "result": None,
        "outputs": {"contract_text": load_pdf_text(pdf_path)},
        "cancelled": False,
        "pdf_path": str(pdf_path),
    }
    background.add_task(_run_job, job_id, pdf_path)
    return AnalyzeStartResponse(job_id=job_id)


@app.get("/analyze/status/{job_id}", response_model=AnalyzeStatusResponse)
async def analyze_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return AnalyzeStatusResponse(job_id=job_id, status="error", step=0, total_steps=4, message="job not found", result=None)
    return AnalyzeStatusResponse(
        job_id=job_id,
        status=job.get("status", "pending"),
        step=int(job.get("step", 0)),
        total_steps=int(job.get("total_steps", 4)),
        message=job.get("message"),
        current_agent=job.get("current_agent"),
        current_label=job.get("current_label"),
        result=job.get("result"),
        partials=job.get("outputs"),
    )


@app.post("/analyze/cancel/{job_id}")
async def analyze_cancel(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return {"error": "job not found"}
    job["cancelled"] = True
    if job.get("status") not in {"done", "error", "cancelled"}:
        job["status"] = "cancelled"
        job["message"] = "Stopped by user"
    return {"ok": True}


@app.post("/analyze/clear/{job_id}")
async def analyze_clear(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return {"ok": True}
    # Try to remove uploaded file
    try:
        p = job.get("pdf_path")
        if p:
            Path(p).unlink(missing_ok=True)
    except Exception:
        pass
    # Drop job from memory
    try:
        JOBS.pop(job_id, None)
    except Exception:
        pass
    return {"ok": True}


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
