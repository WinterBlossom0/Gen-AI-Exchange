from __future__ import annotations

import json
import os
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Callable, Optional
import time

from crewai import Crew, Process, Task
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from src.utils.pdf_loader import load_pdf_text
from src.utils.emailer import send_email
from src.utils.chunker import chunk_by_words
from src.agents.contract_agents import (
    make_alert_agent,
    make_chat_agent,
    make_commercial_agent,
    make_legal_risk_agent,
    make_mitigation_agent,
    make_purpose_agent,
)
from src.tasks.contract_tasks import (
    alert_task,
    commercial_task,
    legal_risk_task,
    mitigation_task,
    purpose_task,
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


def _resolve_model() -> str:
    """Resolve the inference model string.

    Priority:
    1) Requires GEMINI_API_KEY and defaults to Gemini 2.5 Flash Lite.
    2) No Ollama fallback. If key missing, raise a clear error.
    """
    # Sensible request timeout by default (seconds). Override with LITELLM_TIMEOUT or TASK_TIMEOUT_SEC.
    default_timeout = os.getenv("LITELLM_TIMEOUT") or os.getenv("TASK_TIMEOUT_SEC") or "240"
    os.environ["LITELLM_TIMEOUT"] = default_timeout

    # Enforce Gemini-only; allow either GEMINI_API_KEY or GOOGLE_CLOUD_API_KEY
    gemini_key = os.getenv("GEMINI_API_KEY")
    google_key = os.getenv("GOOGLE_CLOUD_API_KEY")
    if not (gemini_key or google_key):
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_CLOUD_API_KEY is required. No Ollama fallback is allowed.")
    # If only GOOGLE_CLOUD_API_KEY provided, mirror into GEMINI_API_KEY for provider libs that expect it
    if not gemini_key and google_key:
        os.environ["GEMINI_API_KEY"] = google_key
    # Default thinking budget to 0 unless explicitly overridden
    os.environ.setdefault("GEMINI_THINKING_BUDGET", "0")
    # crewai/LLM (via litellm) understands provider-prefixed names, e.g., "gemini/<model>"
    return os.getenv("MODEL", "gemini/gemini-2.5-flash")

# Back-compat alias (imports in backend may still use this name)
_resolve_ollama_model = _resolve_model


def run_analysis(contract_path: Path, model: str | None = None) -> AnalysisResult:
    outputs: Dict[str, Any] = {}
    for label, out in run_analysis_iter(contract_path, model=model):
        outputs[label] = out
    return AnalysisResult(
        purpose=str(outputs.get("purpose", "")),
        commercial=str(outputs.get("commercial", "")),
        legal_risks=str(outputs.get("legal_risks", "")),
        mitigations=str(outputs.get("mitigations", "")),
        alert=str(outputs.get("alert", "")),
        plain=str(outputs.get("plain", "")),
    )


def build_agents_and_tasks(contract_text: str, model: str | None = None):
    enforced_model = model or _resolve_model()
    # Create independent LLM instances per agent so we can attach schema-specific configs
    def _new_llm():
        return LLM(model=enforced_model) if ('LLM' in globals() and LLM) else None
    # Instantiate agents with separate LLMs
    purpose_agent = make_purpose_agent(_new_llm())
    commercial_agent = make_commercial_agent(_new_llm())
    legal_agent = make_legal_risk_agent(_new_llm())
    mitig_agent = make_mitigation_agent(_new_llm())
    alert_agent = make_alert_agent(_new_llm())
    tasks = [
        purpose_task(purpose_agent),
        commercial_task(commercial_agent),
        legal_risk_task(legal_agent),
        mitigation_task(mitig_agent),
        alert_task(alert_agent),
    ]
    for t in tasks:
        t.description = t.description.replace("{contract_text}", contract_text)

    agents = [purpose_agent, commercial_agent, legal_agent, mitig_agent, alert_agent]
    labels = ["purpose", "commercial", "legal_risks", "mitigations", "alert"]
    return agents, tasks, labels


def run_analysis_iter(contract_path: Path, model: str | None = None, on_partial: Optional[Callable[[str, Dict[str, Any]], None]] = None):
    """Yield (label, output_string) per task sequentially."""
    text = load_pdf_text(contract_path)
    # Configure chunking
    try:
        chunk_tokens = int(os.getenv("CHUNK_TOKENS", "45000"))
    except ValueError:
        chunk_tokens = 45000
    try:
        chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "500"))
    except ValueError:
        chunk_overlap = 500
    chunks = chunk_by_words(text, chunk_tokens=chunk_tokens, overlap_tokens=chunk_overlap)
    enforced_model = model or _resolve_model()
    agents, tasks, labels = build_agents_and_tasks(text, enforced_model)

    outputs: Dict[str, str] = {}

    def _run_single(agent, task, dbg_label: str = "") -> str:
        agents_list = [agent] if agent is not None else []
        crew = Crew(agents=agents_list, tasks=[task], process=Process.sequential, verbose=False)
        # Enforce per-task timeout
        timeout_sec = int(os.getenv("TASK_TIMEOUT_SEC", os.getenv("LITELLM_TIMEOUT", "240")))
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(crew.kickoff)
            _ = fut.result(timeout=timeout_sec)
        raw = task.output.raw if hasattr(task, "output") else str(task.output)

        # DEBUG: Log raw output for debugging
        print(f"\n=== DEBUG: {dbg_label} RAW OUTPUT ===")
        print(f"Raw output: {repr(raw)}")
        print("=== END DEBUG ===\n")

        return raw

    def _safe_json_list(val: str):
            try:
                data = json.loads(val)
                return data if isinstance(data, list) else []
            except Exception:
                return []

    def _merge_risks(risks_list):
        def score(r):
            sev = (r.get("severity", "").lower())
            s = 3 if sev == "high" else 2 if sev == "medium" else 1 if sev == "low" else 0
            if str(r.get("fairness", "").lower()) == "unfair":
                s += 1
            return s
        by_clause: Dict[str, Dict[str, Any]] = {}
        for r in risks_list:
            clause = str(r.get("clause", "")).strip()
            if not clause:
                continue
            key = clause.lower()
            if key not in by_clause or score(r) > score(by_clause[key]):
                by_clause[key] = r
        merged = sorted(by_clause.values(), key=score, reverse=True)
        return merged[:8]

    def _merge_mitigations(mits_list, keep_for_clauses):
        wanted = {c.lower() for c in keep_for_clauses}
        picked = []
        seen = set()
        for m in mits_list:
            clause = str(m.get("clause", ""))
            if not clause:
                continue
            key = clause.lower()
            if key in seen:
                continue
            if key in wanted:
                picked.append(m)
                seen.add(key)
        if len(picked) < 8:
            for m in mits_list:
                clause = str(m.get("clause", ""))
                key = clause.lower()
                if not clause or key in seen:
                    continue
                picked.append(m)
                seen.add(key)
                if len(picked) >= 8:
                    break
        return picked[:8]

    def _alert_from_risks(risks):
        unfair = [r for r in risks if str(r.get("fairness", "").lower()) == "unfair"]
        high_unfair = [r for r in unfair if str(r.get("severity", "").lower()) == "high"]
        exploit = bool(len(high_unfair) >= 1 or len(unfair) >= 3)
        top_clauses = [r.get("clause", "") for r in risks[:5] if r.get("clause")]
        rationale = (
            f"{len(unfair)} unfair clause(s), {len(high_unfair)} high severity. "
            + ("Leans exploitative." if exploit else "Overall balanced/negotiable.")
        )
        return json.dumps({
            "exploitative": exploit,
            "rationale": rationale,
            "top_unfair_clauses": top_clauses,
        }, ensure_ascii=False)

    # No chunking or combining; single full-context pass per task

    for agent, task, label in zip(agents, tasks, labels):
        # Purpose and alert: single full-context run
        if label in ("purpose", "alert"):
            out_raw = _run_single(agent, task, label)
            out = out_raw or ""
            if on_partial:
                try:
                    on_partial(label, {f"{label}_raw": out_raw})
                except Exception:
                    pass
            if on_partial:
                on_partial(label, {label: out, f"{label}_raw": out, "_progress": 1.0})
            outputs[label] = str(out or "")
            yield label, str(out or "")
            continue

        # Chunked tasks: commercial, legal_risks, mitigations
        raw_concat_parts: list[str] = []
        for i, ctext in enumerate(chunks, start=1):
            # Replace contract_text placeholder per chunk
            t = Task(description=task.description.replace(text, ctext), agent=agent, expected_output=task.expected_output)
            out_raw = _run_single(agent, t, f"{label}#chunk-{i}")
            raw_concat_parts.append(out_raw or "")
            if on_partial:
                on_partial(label, {f"{label}_raw": out_raw, "_chunk": i, "_progress": i / max(1, len(chunks))})
        out = "\n".join(raw_concat_parts).strip()
        if on_partial:
            on_partial(label, {label: out, f"{label}_raw": out, "_progress": 1.0})
        outputs[label] = str(out or "")
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


def save_report(result: AnalysisResult, out_dir: Path, contract_name: str, model: Optional[str] = None, raw: Optional[Dict[str, str]] = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Report naming / retention controlled by env
    versioning = os.getenv("REPORT_VERSIONING", "false").lower() == "true"
    retention = int(os.getenv("REPORT_RETENTION", "3")) if versioning else 0
    ts = time.strftime("%Y%m%d-%H%M%S")
    fname = f"{contract_name}_{ts}_analysis.json" if versioning else f"{contract_name}_analysis.json"
    out_path = out_dir / fname
    # Robust JSON extraction using sanitizer
    from src.utils.json_sanitizer import extract_json_array, extract_json_object
    def _bullets(text: str, n=10):
        if not text:
            return []
        lines = [l.strip().lstrip("-*• ") for l in text.splitlines() if l.strip()]
        if lines:
            return lines[:n]
        chunks = [c.strip() for c in text.split(". ") if c.strip()]
        return chunks[:n]
    def _no_thought(text: str) -> str:
        if not text:
            return text
        banned = ("plan:", "analysis:", "thought:", "internal:")
        out_lines = []
        for l in (text.splitlines()):
            if not l.strip():
                continue
            low = l.strip().lower()
            if any(low.startswith(b) for b in banned):
                continue
            if low in ("plan", "analysis", "thought", "internal"):
                continue
            if low.startswith("```"):
                continue
            out_lines.append(l)
        return "\n".join(out_lines).strip()

    # Canonical parsed structures (computed on demand if raw-only disabled)
    commercial_parsed = extract_json_array(result.commercial)
    legal_risks_parsed = extract_json_array(result.legal_risks)
    mitigations_parsed = extract_json_array(result.mitigations)
    alert_parsed = extract_json_object(result.alert)

    # Normalize mitigation negotiation_points to array of strings when possible
    def _norm_mitigations(mits):
        norm = []
        for m in (mits or []):
            if not isinstance(m, dict):
                continue
            mm = dict(m)
            pts = mm.get("negotiation_points")
            if isinstance(pts, str):
                # split by lines or bullets
                parts = [p.strip(" -*•\t") for p in pts.splitlines() if p.strip()]
                mm["negotiation_points"] = parts if parts else [pts]
            elif isinstance(pts, list):
                mm["negotiation_points"] = [str(p) for p in pts]
            norm.append(mm)
        return norm
    mitigations_parsed = _norm_mitigations(mitigations_parsed)

    raw_only = os.getenv("REPORT_RAW_ONLY", "true").lower() == "true"
    if raw_only:
        # Save only raw + minimal meta; parsing will be done on read
        report = {
            "raw": {
                "purpose": (raw.get("purpose") if raw else result.purpose),
                "commercial": (raw.get("commercial") if raw else result.commercial),
                "legal_risks": (raw.get("legal_risks") if raw else result.legal_risks),
                "mitigations": (raw.get("mitigations") if raw else result.mitigations),
                "alert": (raw.get("alert") if raw else result.alert),
                "plain": (raw.get("plain") if raw else result.plain),
            },
            "meta": {
                "contract": contract_name,
                "model": model or os.getenv("MODEL", "gemini/gemini-2.5-flash"),
                "saved_at": ts,
            }
        }
    else:
        # Canonical report schema consumed by the UI
        report = {
            "purpose": _no_thought(result.purpose),
            "plain": _no_thought(result.plain),
            "plain_bullets": _bullets(_no_thought(result.plain), 10),
            "commercial": commercial_parsed,              # always an array
            "legal_risks": legal_risks_parsed,            # always an array
            "mitigations": mitigations_parsed,            # always an array
            "decision": alert_parsed,                     # always an object (or empty {})
            "meta": {
                "contract": contract_name,
                "model": model or os.getenv("MODEL", "gemini/gemini-2.5-flash"),
                "saved_at": ts,
            }
        }
        # Persist raw outputs as-is alongside canonical when provided
        if raw:
            report["raw"] = {
                "purpose": raw.get("purpose", result.purpose),
                "commercial": raw.get("commercial", result.commercial),
                "legal_risks": raw.get("legal_risks", result.legal_risks),
                "mitigations": raw.get("mitigations", result.mitigations),
                "alert": raw.get("alert", result.alert),
                "plain": raw.get("plain", result.plain),
            }

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Always write a companion raw JSON file with only raw strings
    raw_fname = f"{contract_name}_{ts}_raw.json" if versioning else f"{contract_name}_raw.json"
    raw_path = out_dir / raw_fname
    raw_report = {
        "purpose": (raw.get("purpose") if raw else result.purpose),
        "commercial": (raw.get("commercial") if raw else result.commercial),
        "legal_risks": (raw.get("legal_risks") if raw else result.legal_risks),
        "mitigations": (raw.get("mitigations") if raw else result.mitigations),
        "alert": (raw.get("alert") if raw else result.alert),
        "plain": (raw.get("plain") if raw else result.plain),
        "meta": {
            "contract": contract_name,
            "model": model or os.getenv("MODEL", "gemini/gemini-2.5-flash"),
            "saved_at": ts,
            "pair": out_path.name,
        },
    }
    with raw_path.open("w", encoding="utf-8") as rf:
        json.dump(raw_report, rf, ensure_ascii=False, indent=2)

    # Also write a single unfiltered raw .txt file containing exact agent outputs
    raw_txt_name = f"{contract_name}_{ts}_raw.txt" if versioning else f"{contract_name}_raw.txt"
    raw_txt_path = out_dir / raw_txt_name
    try:
        purpose_txt = (raw.get("purpose") if raw else result.purpose) or ""
        commercial_txt = (raw.get("commercial") if raw else result.commercial) or ""
        legal_txt = (raw.get("legal_risks") if raw else result.legal_risks) or ""
        mitigations_txt = (raw.get("mitigations") if raw else result.mitigations) or ""
        alert_txt = (raw.get("alert") if raw else result.alert) or ""
        plain_txt = (raw.get("plain") if raw else result.plain) or ""

        # Compose with minimal section headers, without modifying agent outputs
        sections = [
            f"===== PURPOSE =====\n{purpose_txt}",
            f"===== COMMERCIAL =====\n{commercial_txt}",
            f"===== LEGAL_RISKS =====\n{legal_txt}",
            f"===== MITIGATIONS =====\n{mitigations_txt}",
            f"===== ALERT =====\n{alert_txt}",
            f"===== PLAIN =====\n{plain_txt}",
        ]
        with raw_txt_path.open("w", encoding="utf-8", newline="\n") as tf:
            tf.write("\n\n".join(sections).strip() + "\n")
    except Exception:
        # Fail silently; JSON and MD artifacts still exist
        pass
    # Enforce retention policy for versioned reports
    if versioning and retention > 0:
        prefix = f"{contract_name}_"
        files = sorted([p for p in out_dir.glob(f"{contract_name}_*_analysis.json")], key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[retention:]:
            try:
                old.unlink(missing_ok=True)
            except Exception:
                pass
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
    model = _resolve_model()

    contracts_dir = Path("contracts")
    pdf_path = contracts_dir / "Master-Services-Agreement.pdf"

    if not pdf_path.exists():
        console.print(Panel.fit(f"Could not find PDF at {pdf_path}", title="Error", style="red"))
        raise SystemExit(1)

    console.print(Panel.fit(f"Analyzing {pdf_path.name}", title="CrewAI Contract Analysis"))

    result = run_analysis(pdf_path, model=model)

    out_path = save_report(result, Path("reports"), pdf_path.stem, model=model)
    console.print(Panel.fit(f"Report saved to {out_path}", title="Done", style="green"))

    maybe_send_alert(result.alert, pdf_path.name)


if __name__ == "__main__":
    main()
