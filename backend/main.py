from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.main import run_analysis, run_analysis_iter, save_report, maybe_send_alert, _resolve_model as _resolve_ollama_model, AnalysisResult, build_agents_and_tasks  # type: ignore
from src.utils.pdf_loader import load_pdf_text  # type: ignore
from src.utils.emailer import load_smtp_config, send_email  # type: ignore

app = FastAPI(title="Contract Analyzer API")
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    # Production frontend domains
    "https://gen-ai-exchange-legal-agent.onrender.com",
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

app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")

JOBS: Dict[str, Dict[str, Any]] = {}
FILES: Dict[str, Dict[str, Any]] = {}


class AnalyzeResponse(BaseModel):
    report_json_path: str
    report_file: str
    report_url: str
    raw_report_url: str | None = None
    raw_text_url: str | None = None
    exploitative: Optional[bool] = None
    rationale: Optional[str] = None
    # Echo key sections to power the UI (raw strings)
    contract_text: str
    purpose: str
    commercial: str
    legal_risks: str
    mitigations: str
    alert: str
    plain: str
    # Raw agent outputs for transparency/debugging
    debug_raw: Optional[Dict[str, Any]] = None


class UploadResponse(BaseModel):
    file_id: str
    file_name: str
    contract_text: str


class SectionRequest(BaseModel):
    file_id: str
    label: str  # one of: purpose|commercial|legal_risks|mitigations|alert
    recipient: Optional[str] = None


class SectionResponse(BaseModel):
    label: str
    output: str


class FinalizeRequest(BaseModel):
    file_id: str
    purpose: str
    commercial: str
    legal_risks: str
    mitigations: str
    alert: str
    plain: Optional[str] = None


class FinalizeResponse(BaseModel):
    report_json_path: str
    report_file: str
    report_url: str
    raw_report_url: str
    raw_text_url: str
    contract_text: str


class TestEmailRequest(BaseModel):
    to: Optional[str] = None
    include_pdf: bool = False


class TestEmailResponse(BaseModel):
    ok: bool
    message: str


class EmailConfigResponse(BaseModel):
    host_set: bool
    port: int
    username_set: bool
    use_tls: bool
    from_addr_set: bool

@app.get("/api/reports/list")
def api_list_reports():
    try:
        files = []
        for p in REPORTS_DIR.glob("*_analysis.json"):
            files.append({
                "name": p.name,
                "size": p.stat().st_size,
                "mtime": p.stat().st_mtime,
                "url": f"/reports/{p.name}",
            })
        files.sort(key=lambda x: x["mtime"], reverse=True)
        return {"reports": files}
    except Exception as e:
        return {"error": f"failed to list reports: {e}"}


def _sanitize_plain(text: str) -> str:
    """Basic formatting cleanup only - no content filtering."""
    if not text:
        return text
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return "\n".join(lines)

def _sanitize_no_thought(text: str) -> str:
    if not text:
        return text
    lines = [l for l in (text.splitlines()) if l.strip()]
    banned = ("plan:", "analysis:", "thought:", "internal:")
    out = []
    for l in lines:
        low = l.strip().lower()
        if any(low.startswith(b) for b in banned):
            continue
        if low in ("plan", "analysis", "thought", "internal"):
            continue
        if low.startswith("```"):
            continue
        out.append(l)
    return "\n".join(out).strip()


def _sanitize_chat_answer(text: str, question: str) -> str:
    """Basic formatting cleanup only - no content filtering."""
    if not text:
        return text
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return "Not stated in the contract."
    # Just return clean lines, no content validation
    return "\n".join(lines[:3])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload", response_model=UploadResponse)
async def upload_contract(file: UploadFile = File(...)):
    contents = await file.read()
    pdf_path = UPLOADS_DIR / file.filename
    with pdf_path.open("wb") as f:
        f.write(contents)
    file_id = os.urandom(8).hex()
    FILES[file_id] = {"path": str(pdf_path), "name": file.filename}
    return UploadResponse(file_id=file_id, file_name=file.filename, contract_text=load_pdf_text(pdf_path))


@app.post("/analyze/section", response_model=SectionResponse)
async def analyze_section(req: SectionRequest):
    # Validate
    info = FILES.get(req.file_id)
    if not info:
        return SectionResponse(label=req.label, output="")
    pdf_path = Path(info["path"])
    if not pdf_path.exists():
        return SectionResponse(label=req.label, output="")

    # Build single agent+task for the given label
    model = _resolve_ollama_model()
    text = load_pdf_text(pdf_path)
    agents, tasks, labels = build_agents_and_tasks(text, model)
    if req.label not in labels:
        return SectionResponse(label=req.label, output="")
    idx = labels.index(req.label)

    from crewai import Crew, Process  # type: ignore
    agent = agents[idx]
    task = tasks[idx]
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    _ = crew.kickoff()
    try:
        raw = task.output.raw if hasattr(task, "output") else str(task.output)
    except Exception:
        raw = ""

    # Optional email on alert
    if req.label == "alert":
        try:
            maybe_send_alert(raw, pdf_path.name, pdf_path=pdf_path, recipient_override=req.recipient)
        except Exception:
            pass

    return SectionResponse(label=req.label, output=str(raw or ""))


@app.post("/analyze/finalize", response_model=FinalizeResponse)
async def analyze_finalize(req: FinalizeRequest):
    info = FILES.get(req.file_id)
    if not info:
        return {"error": "file not found"}  # type: ignore
    pdf_path = Path(info["path"])
    model = _resolve_ollama_model()
    # Build a result object and persist
    result = AnalysisResult(
        purpose=req.purpose,
        commercial=req.commercial,
        legal_risks=req.legal_risks,
        mitigations=req.mitigations,
        alert=req.alert,
        plain=req.plain or "",
    )
    raw_payload = {
        "purpose": req.purpose,
        "commercial": req.commercial,
        "legal_risks": req.legal_risks,
        "mitigations": req.mitigations,
        "alert": req.alert,
        "plain": req.plain or "",
    }
    out_path = save_report(result, REPORTS_DIR, pdf_path.stem, model=model, raw=raw_payload)
    name = out_path.name
    url = f"/reports/{name}"
    raw_name = name.replace("_analysis.json", "_raw.json")
    raw_url = f"/reports/{raw_name}"
    raw_txt = name.replace("_analysis.json", "_raw.txt")
    raw_txt_url = f"/reports/{raw_txt}"

    return FinalizeResponse(
        report_json_path=str(out_path),
        report_file=name,
        report_url=url,
        raw_report_url=raw_url,
        raw_text_url=raw_txt_url,
        contract_text=load_pdf_text(pdf_path),
    )


@app.post("/upload/clear/{file_id}")
async def upload_clear(file_id: str):
    info = FILES.pop(file_id, None)
    if not info:
        return {"ok": True}
    try:
        p = Path(info.get("path", ""))
        if p.exists():
            p.unlink(missing_ok=True)
    except Exception:
        pass
    return {"ok": True}


@app.get("/email/config", response_model=EmailConfigResponse)
async def email_config():
    try:
        cfg = load_smtp_config()
        return EmailConfigResponse(
            host_set=bool(cfg.host),
            port=int(cfg.port or 0),
            username_set=bool(cfg.username),
            use_tls=bool(cfg.use_tls),
            from_addr_set=bool(cfg.from_addr or cfg.username)
        )
    except Exception:
        # Report "not set" without leaking details
        return EmailConfigResponse(host_set=False, port=0, username_set=False, use_tls=True, from_addr_set=False)


@app.post("/email/test", response_model=TestEmailResponse)
async def email_test(req: TestEmailRequest):
    try:
        cfg = load_smtp_config()
    except Exception as e:
        return TestEmailResponse(ok=False, message=f"SMTP config error: {e}")

    to_addr = req.to or os.getenv("ALERT_TO_EMAIL") or cfg.from_addr or cfg.username
    if not to_addr:
        return TestEmailResponse(ok=False, message="No recipient. Provide 'to' or set ALERT_TO_EMAIL/ALERT_FROM_EMAIL.")
    try:
        attachments = []
        if req.include_pdf:
            # Try attach any last uploaded file if available
            last = next(iter(FILES.values()), None)
            if last and last.get("path"):
                attachments = [last["path"]]
        send_email(to_addr, "Contract Analyzer SMTP Test", "This is a test email from the Contract Analyzer backend.", attachments=attachments)
        return TestEmailResponse(ok=True, message=f"Sent to {to_addr}")
    except Exception as e:
        return TestEmailResponse(ok=False, message=f"Send failed: {e}")


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_contract(file: UploadFile = File(...), recipient: Optional[str] = Form(default=None)):
    # Save uploaded file
    contents = await file.read()
    pdf_path = UPLOADS_DIR / file.filename
    with pdf_path.open("wb") as f:
        f.write(contents)

    # Resolve model (Gemini-only) and run analysis
    model = _resolve_ollama_model()
    result = run_analysis(pdf_path, model=model)
    raw_payload = {
        "purpose": result.purpose,
        "commercial": result.commercial,
        "legal_risks": result.legal_risks,
        "mitigations": result.mitigations,
        "alert": result.alert,
        "plain": result.plain,
    }
    out_path = save_report(result, REPORTS_DIR, pdf_path.stem, model=model, raw=raw_payload)
    name = out_path.name
    url = f"/reports/{name}"
    # derive raw pair filename
    raw_name = name.replace("_analysis.json", "_raw.json")
    raw_url = f"/reports/{raw_name}"
    raw_txt = name.replace("_analysis.json", "_raw.txt")
    raw_txt_url = f"/reports/{raw_txt}"

    # Use raw strings as-is for UI
    exploitative = None
    rationale = None
    purpose_text = result.purpose

    # Optional email alert
    # Optional email alert with attachment and recipient override
    try:
        maybe_send_alert(result.alert, pdf_path.name, pdf_path=pdf_path, recipient_override=recipient)
    except Exception:
        pass

    # Build final plain: sanitize formatting + remove potential internal thought lines
    final_plain = _sanitize_no_thought(_sanitize_plain(result.plain))

    debug_payload = {
        "purpose": purpose_text,
        "commercial": result.commercial,
        "legal_risks": result.legal_risks,
        "mitigations": result.mitigations,
        "alert": result.alert,
        "plain": final_plain,
    }
    return AnalyzeResponse(
        report_json_path=str(out_path),
        report_file=name,
        report_url=url,
        exploitative=exploitative,
        rationale=rationale,
        contract_text=load_pdf_text(pdf_path),
        purpose=purpose_text,
        commercial=result.commercial,
        legal_risks=result.legal_risks,
        mitigations=result.mitigations,
        alert=result.alert,
        plain=final_plain,
        raw_report_url=raw_url,
        raw_text_url=raw_txt_url,
        debug_raw=debug_payload,
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
    # Raw outputs for debugging
    debug_raw: Optional[Dict[str, Any]] = None


def _run_job(job_id: str, pdf_path: Path):
    import traceback
    try:
        j = JOBS.get(job_id)
        if not j:
            return
        j["status"] = "running"
        j["step"] = 0
        j["message"] = "Starting"
        j["outputs"] = j.get("outputs") or {}
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
        ]
        total = len(steps) + 1  # +1 for saving report
        JOBS[job_id]["total_steps"] = total

        # Iterate tasks sequentially and update status
        def _on_partial(part_label: str, data: Dict[str, Any]):
            job = JOBS.get(job_id)
            if not job or job.get("cancelled"):
                return
            # indicate which label is currently streaming
            job["current_label"] = part_label
            job["message"] = "Running"
            cur = job.get("outputs") or {}
            cur.update(data)
            job["outputs"] = cur

        for idx, (label, out) in enumerate(run_analysis_iter(pdf_path, model=model, on_partial=_on_partial), start=1):
            if JOBS.get(job_id, {}).get("cancelled"):
                JOBS[job_id]["message"] = "Cancelled"
                JOBS[job_id]["status"] = "cancelled"
                return
            # Find friendly agent name
            agent_name = next((name for name, lab in steps if lab == label), label)
            job = JOBS.get(job_id)
            if not job or job.get("cancelled"):
                return
            job["step"] = idx
            job["message"] = "Running"
            job["current_agent"] = agent_name
            job["current_label"] = label
            outputs[label] = out
            # Update partials for frontend
            part: Dict[str, Any] = {label: out, f"{label}_raw": out}
            # no parsing or transformation; keep exactly as returned
            # merge into job outputs (race-safe if job was cleared or cancelled)
            job_now = JOBS.get(job_id)
            if job_now and not job_now.get("cancelled"):
                cur = (job_now.get("outputs") or {}).copy()
                cur.update(part)
                job_now["outputs"] = cur

        job = JOBS.get(job_id)
        if not job:
            return
        if job.get("cancelled"):
            job["message"] = "Cancelled"
            job["status"] = "cancelled"
            return
        job["step"] = total
        JOBS[job_id]["message"] = "Saving report"
        # Build final plain formatting only
        plain_raw = str(outputs.get("plain", ""))
        plain_sane = _sanitize_no_thought(_sanitize_plain(plain_raw))

        analysis_result = AnalysisResult(
            purpose=str(outputs.get("purpose", "")),
            commercial=str(outputs.get("commercial", "")),
            legal_risks=str(outputs.get("legal_risks", "")),
            mitigations=str(outputs.get("mitigations", "")),
            alert=str(outputs.get("alert", "")),
            plain=plain_sane,
        )
        # Collect raw outputs as-is, preferring *_raw captured earlier
        job_out = (JOBS.get(job_id, {}).get("outputs") or {})
        raw_payload = {
            "purpose": str(job_out.get("purpose_raw", outputs.get("purpose", ""))),
            "commercial": str(job_out.get("commercial_raw", outputs.get("commercial", ""))),
            "legal_risks": str(job_out.get("legal_risks_raw", outputs.get("legal_risks", ""))),
            "mitigations": str(job_out.get("mitigations_raw", outputs.get("mitigations", ""))),
            "alert": str(job_out.get("alert_raw", outputs.get("alert", ""))),
            "plain": str(outputs.get("plain", "")),
        }
        out_path = save_report(analysis_result, REPORTS_DIR, pdf_path.stem, model=model, raw=raw_payload)
        name = out_path.name
        url = f"/reports/{name}"
        raw_name = name.replace("_analysis.json", "_raw.json")
        raw_url = f"/reports/{raw_name}"
        raw_txt = name.replace("_analysis.json", "_raw.txt")
        raw_txt_url = f"/reports/{raw_txt}"

        # No parsing; keep values as-is
        exploitative = None
        rationale = None
        purpose_text = analysis_result.purpose

        # Reconstruct a result-like object from raw job outputs for debugging
        debug_payload = {
            "purpose": str(job_out.get("purpose_raw", analysis_result.purpose)),
            "commercial": str(job_out.get("commercial_raw", analysis_result.commercial)),
            "legal_risks": str(job_out.get("legal_risks_raw", analysis_result.legal_risks)),
            "mitigations": str(job_out.get("mitigations_raw", analysis_result.mitigations)),
            "alert": str(job_out.get("alert_raw", analysis_result.alert)),
            "plain": plain_sane,
        }
        JOBS[job_id]["result"] = AnalyzeResponse(
            report_json_path=str(out_path),
            report_file=name,
            report_url=url,
            raw_report_url=raw_url,
            raw_text_url=raw_txt_url,
            exploitative=exploitative,
            rationale=rationale,
            contract_text=load_pdf_text(pdf_path),
            purpose=purpose_text,
            commercial=analysis_result.commercial,
            legal_risks=analysis_result.legal_risks,
            mitigations=analysis_result.mitigations,
            alert=analysis_result.alert,
            plain=analysis_result.plain,
            debug_raw=debug_payload,
        )
        job = JOBS.get(job_id)
        if job:
            job["step"] = total
            job["message"] = "Done"
            job["status"] = "done"

        # Send alert email with attachment if exploitative and recipient available
        try:
            recipient = (JOBS.get(job_id) or {}).get("recipient")
            maybe_send_alert(analysis_result.alert, pdf_path.name, pdf_path=pdf_path, recipient_override=recipient)
        except Exception:
            pass
    except Exception as e:
        tb = traceback.format_exc()
        job = JOBS.get(job_id)
        if job:
            job["status"] = "error"
            job["message"] = f"{type(e).__name__}: {e}\n{tb}"


@app.post("/analyze/start", response_model=AnalyzeStartResponse)
async def analyze_start(background: BackgroundTasks, file: UploadFile = File(...), recipient: Optional[str] = Form(default=None)):
    contents = await file.read()
    pdf_path = UPLOADS_DIR / file.filename
    with pdf_path.open("wb") as f:
        f.write(contents)

    job_id = os.urandom(8).hex()
    # Set total_steps to the real count (+1 for saving)
    # Steps: purpose, commercial, legal_risks, mitigations, alert + save
    total_steps = 5 + 1
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
    # Store recipient override in job context for later email sending
    JOBS[job_id]["recipient"] = recipient
    background.add_task(_run_job, job_id, pdf_path)
    return AnalyzeStartResponse(job_id=job_id)


@app.get("/analyze/status/{job_id}", response_model=AnalyzeStatusResponse)
async def analyze_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return AnalyzeStatusResponse(job_id=job_id, status="error", step=0, total_steps=4, message="job not found", result=None)
    # Surface any intermediate raw outputs if present
    outputs = job.get("outputs") or {}
    # Prefer *_raw values when available; fall back to plain keys
    debug_payload = {
        "purpose": outputs.get("purpose_raw") or outputs.get("purpose"),
        "commercial": outputs.get("commercial_raw") or outputs.get("commercial"),
        "legal_risks": outputs.get("legal_risks_raw") or outputs.get("legal_risks"),
        "mitigations": outputs.get("mitigations_raw") or outputs.get("mitigations"),
        "alert": outputs.get("alert_raw") or outputs.get("alert"),
        "plain": outputs.get("plain"),
    }
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
        debug_raw=debug_payload,
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
    # Clear outputs immediately and try to delete uploaded file
    try:
        job["outputs"] = {}
        p = job.get("pdf_path")
        if p:
            Path(p).unlink(missing_ok=True)
    except Exception:
        pass
    return {"ok": True, "status": job.get("status")}


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

    # Use Gemini model for chat agent as well
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
    # Sanitize chat output to remove headings/markdown and enforce brevity
    answer = _sanitize_chat_answer(answer, req.question)

    return {"answer": answer}