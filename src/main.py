from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from crewai import Crew, Process
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from src.utils.pdf_loader import load_pdf_text
from src.utils.emailer import send_email
from src.agents.contract_agents import (
    make_alert_agent,
    make_chat_agent,
    make_commercial_agent,
    make_legal_risk_agent,
    make_mitigation_agent,
    make_purpose_agent,
    make_simplifier_agent,
)
from src.tasks.contract_tasks import (
    alert_task,
    commercial_task,
    legal_risk_task,
    mitigation_task,
    purpose_task,
    simplifier_task,
)
try:
    from crewai import LLM  # type: ignore
except Exception:
    LLM = None  # type: ignore

console = Console()


@dataclass
class AnalysisResult:
    purpose: str
    commercial: str
    legal_risks: str
    mitigations: str
    alert: str
    plain: str


def _resolve_ollama_model() -> str:
    """Return the Ollama model string; default to gemma3:1b.

    No cloud API keys are required. If you're running Ollama on a non-default
    host/port, set OLLAMA_HOST (e.g., http://127.0.0.1:11434).
    """
    # Proactively remove cloud provider keys to avoid accidental usage
    for k in [
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "ANTHROPIC_API_KEY",
        "COHERE_API_KEY",
        "MISTRAL_API_KEY",
        "TOGETHER_API_KEY",
        "OPENROUTER_API_KEY",
        "GROQ_API_KEY",
        "XAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "AZURE_OPENAI_API_KEY",
    ]:
        if k in os.environ:
            os.environ.pop(k, None)
    # Ensure Ollama host envs are set (defaults to local daemon)
    default_host = "http://127.0.0.1:11434"
    if not os.getenv("OLLAMA_HOST"):
        os.environ["OLLAMA_HOST"] = default_host
    if not os.getenv("OLLAMA_API_BASE"):
        os.environ["OLLAMA_API_BASE"] = os.getenv("OLLAMA_HOST", default_host)
    if not os.getenv("OLLAMA_BASE_URL"):
        os.environ["OLLAMA_BASE_URL"] = os.getenv("OLLAMA_HOST", default_host)

    # Allow override via OLLAMA_MODEL; default to gemma3:1b
    model = os.getenv("OLLAMA_MODEL", "ollama/gemma3:1b")
    return model


def run_analysis(contract_path: Path, model: str | None = None) -> AnalysisResult:
    text = load_pdf_text(contract_path)

    # Build agents and tasks
    agents, tasks, labels = build_agents_and_tasks(text, model)

    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff()

    # CrewAI returns a string or dict-like; to keep simple, collect tool outputs off tasks
    outputs: Dict[str, Any] = {}
    for label, task in zip(labels, tasks):
        try:
            # CrewAI task output may be in task.output or returned in result dict; handle robustly
            if hasattr(task, "output") and task.output is not None:
                raw = getattr(task.output, "raw", None)
                outputs[label] = raw if raw is not None else str(task.output)
            elif isinstance(result, dict) and label in result:
                outputs[label] = result[label]
            else:
                outputs[label] = ""
        except Exception:
            outputs[label] = ""

    return AnalysisResult(
        purpose=str(outputs.get("purpose", "")),
        commercial=str(outputs.get("commercial", "")),
        legal_risks=str(outputs.get("legal_risks", "")),
        mitigations=str(outputs.get("mitigations", "")),
        alert=str(outputs.get("alert", "")),
        plain=str(outputs.get("plain", "")),
    )


def build_agents_and_tasks(contract_text: str, model: str | None = None):
    enforced_model = model or _resolve_ollama_model()
    llm = None
    if 'LLM' in globals() and LLM:
        llm = LLM(model=enforced_model)
    # Instantiate agents
    purpose_agent = make_purpose_agent(llm)
    commercial_agent = make_commercial_agent(llm)
    legal_agent = make_legal_risk_agent(llm)
    mitig_agent = make_mitigation_agent(llm)
    alert_agent = make_alert_agent(llm)
    simplifier_agent = make_simplifier_agent(llm)

    # Create tasks
    tasks = [
        purpose_task(purpose_agent),
        commercial_task(commercial_agent),
        legal_risk_task(legal_agent),
        mitigation_task(mitig_agent),
        alert_task(alert_agent),
        simplifier_task(simplifier_agent),
    ]
    # Inject context safely
    for t in tasks:
        t.description = t.description.replace("{contract_text}", contract_text)

    agents = [purpose_agent, commercial_agent, legal_agent, mitig_agent, alert_agent, simplifier_agent]
    labels = ["purpose", "commercial", "legal_risks", "mitigations", "alert", "plain"]
    return agents, tasks, labels


def run_analysis_iter(contract_path: Path, model: str | None = None):
    """Yield (label, output_string) per task sequentially to support progress reporting."""
    text = load_pdf_text(contract_path)
    agents, tasks, labels = build_agents_and_tasks(text, model)
    for agent, task, label in zip(agents, tasks, labels):
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
        _ = crew.kickoff()
        out = ""
        try:
            out = task.output.raw if hasattr(task, "output") else str(task.output)
        except Exception:
            out = ""
        yield label, str(out or "")


def maybe_send_alert(alert_json: str, contract_name: str) -> None:
    try:
        data = json.loads(alert_json)
    except Exception:
        return
    exploitative = bool(data.get("exploitative"))
    recipient = os.getenv("ALERT_TO_EMAIL")
    if exploitative and recipient:
        subject = f"Exploitative contract detected: {contract_name}"
        body = json.dumps(data, indent=2)
        send_email(recipient, subject, body)


def save_report(result: AnalysisResult, out_dir: Path, contract_name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{contract_name}_analysis.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({
            "purpose": result.purpose,
            "commercial": result.commercial,
            "legal_risks": result.legal_risks,
            "mitigations": result.mitigations,
            "alert": result.alert,
            "plain": result.plain,
        }, f, ensure_ascii=False, indent=2)
    # Also write a human-friendly markdown
    md_path = out_dir / f"{contract_name}_analysis.md"
    md = [
        f"# Contract Analysis: {contract_name}",
        "",
        "## In simple terms",
        result.plain or "(No plain-language summary generated)",
        "",
        "## Purpose",
        result.purpose,
        "",
        "## Commercial terms",
        result.commercial,
        "",
        "## Legal risks",
        result.legal_risks,
        "",
        "## Mitigations",
        result.mitigations,
        "",
        "## Exploitative decision",
        result.alert,
    ]
    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md))
    return out_path


def main():
    load_dotenv()
    # Use local Ollama model (no cloud keys)
    model = _resolve_ollama_model()

    contracts_dir = Path("contracts")
    pdf_path = contracts_dir / "Master-Services-Agreement.pdf"

    if not pdf_path.exists():
        console.print(Panel.fit(f"Could not find PDF at {pdf_path}", title="Error", style="red"))
        raise SystemExit(1)

    console.print(Panel.fit(f"Analyzing {pdf_path.name}", title="CrewAI Contract Analysis"))

    result = run_analysis(pdf_path, model=model)

    out_path = save_report(result, Path("reports"), pdf_path.stem)
    console.print(Panel.fit(f"Report saved to {out_path}", title="Done", style="green"))

    maybe_send_alert(result.alert, pdf_path.name)


if __name__ == "__main__":
    main()
