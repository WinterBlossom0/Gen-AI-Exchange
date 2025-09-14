from __future__ import annotations

import json
import os
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Callable, Optional

from crewai import Crew, Process, Task
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

    # Timeout policy: default to effectively "no timeout" unless user overrides.
    # Some wrappers treat 0 as immediate timeout; use a very large number (1 year in seconds).
    # You can still override via TASK_TIMEOUT_SEC or LITELLM_TIMEOUT env vars.
    very_long_timeout = os.getenv("TASK_TIMEOUT_SEC") or os.getenv("LITELLM_TIMEOUT") or str(365 * 24 * 60 * 60)
    os.environ["LITELLM_TIMEOUT"] = very_long_timeout
    os.environ.setdefault("LITELLM_MAX_RETRIES", "1")

    # Allow override via OLLAMA_MODEL; default to gemma3:1b
    model = os.getenv("OLLAMA_MODEL", "ollama/gemma3:1b")
    return model


def run_analysis(contract_path: Path, model: str | None = None) -> AnalysisResult:
    # Reuse iterator path to leverage chunked heavy-task processing
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
    # Inject full contract text for all base tasks; chunking logic will handle very large inputs per-step
    for t in tasks:
        t.description = t.description.replace("{contract_text}", contract_text)

    agents = [purpose_agent, commercial_agent, legal_agent, mitig_agent, alert_agent, simplifier_agent]
    labels = ["purpose", "commercial", "legal_risks", "mitigations", "alert", "plain"]
    return agents, tasks, labels


def run_analysis_iter(contract_path: Path, model: str | None = None, on_partial: Optional[Callable[[str, Dict[str, Any]], None]] = None):
    """Yield (label, output_string) per task sequentially to support progress reporting.
    Heavy tasks (legal_risks, mitigations) are chunked and can run partially in parallel.
    The alert decision is derived from merged risks to avoid long calls.
    """
    text = load_pdf_text(contract_path)
    enforced_model = model or _resolve_ollama_model()
    agents, tasks, labels = build_agents_and_tasks(text, enforced_model)

    # Keep outputs so alert can use risks
    outputs: Dict[str, str] = {}

    # Helpers to run a single task and get output string
    def _run_single(agent, task) -> str:
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
        _ = crew.kickoff()
        try:
            return task.output.raw if hasattr(task, "output") else str(task.output)
        except Exception:
            return ""

    # Chunking helpers
    def _chunk_text(txt: str, chunk_chars: int, overlap: int = 400):
        if len(txt) <= chunk_chars:
            return [txt]
        chunks = []
        i = 0
        while i < len(txt):
            end = min(len(txt), i + chunk_chars)
            chunks.append(txt[i:end])
            if end == len(txt):
                break
            i = max(end - overlap, i + 1)
        return chunks

    def _safe_json_list(val: str):
        try:
            data = json.loads(val)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _merge_risks(risks_list):
        # Deduplicate by normalized clause text; rank by severity and unfairness
        def score(r):
            sev = (r.get("severity", "").lower())
            s = 3 if sev == "high" else 2 if sev == "medium" else 1 if sev == "low" else 0
            if str(r.get("fairness", "")).lower() == "unfair":
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
        # Keep items matching the top risk clauses first
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
        # If fewer than 8, fill with the rest
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
        unfair = [r for r in risks if str(r.get("fairness", "")).lower() == "unfair"]
        high_unfair = [r for r in unfair if str(r.get("severity", "")).lower() == "high"]
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

    # Utility to summarize multiple partial outputs for purpose/plain
    def _combine_summaries(agent_factory, base_task_factory, parts: list[str], title: str) -> str:
        if title == "plain":
            combined_prompt = (
                "Combine these partial plain-language notes into a single simple summary for non-lawyers. "
                "Write 8–10 bullet points only (no intro/outro), each ≤140 characters. Start lines with You:, They:, or Both:. "
                "Keep key points, remove duplicates, and keep wording very simple.\n\n" +
                "\n\n".join([f"Part {i+1}:\n{p}" for i, p in enumerate(parts)])
            )
        else:
            combined_prompt = (
                f"Combine and compress the following partial {title} into a single concise result. "
                f"Keep all key points; remove duplicates. Keep under 80 words. Use 2–3 short sentences.\n\n" +
                "\n\n".join([f"Part {i+1}:\n{p}" for i, p in enumerate(parts)])
            )
        if 'LLM' in globals() and LLM:
            llm = LLM(model=enforced_model)
        else:
            llm = None
        agent = agent_factory(llm)
        # Create a one-off task to combine
        task = Task(description=combined_prompt, agent=agent, expected_output=f"Combined {title}")
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
        _ = crew.kickoff()
        try:
            return task.output.raw if hasattr(task, "output") else str(task.output)
        except Exception:
            return ""

    # Main loop with special handling for heavy steps
    for agent, task, label in zip(agents, tasks, labels):
        if label in ("legal_risks", "mitigations"):
            # Build chunk tasks
            CHUNK_CHARS = int(os.getenv("CHUNK_CHARS", "6000"))
            CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "600"))
            env_par = os.getenv("CHUNK_PARALLEL")
            if env_par:
                PAR = max(1, int(env_par))
            else:
                cpu = os.cpu_count() or 2
                PAR = max(2, cpu)  # default: use all available cores
            chunks = _chunk_text(text, CHUNK_CHARS, CHUNK_OVERLAP)
            PAR = min(PAR, max(1, len(chunks)))

            # Build a fresh task per chunk
            def build_chunk_task(chunk_text: str):
                # Build a fresh agent per chunk to avoid any cross-run state and allow safe parallelism
                from src.tasks.contract_tasks import legal_risk_task, mitigation_task  # local import to avoid cycles
                if 'LLM' in globals() and LLM:
                    llm = LLM(model=enforced_model)
                else:
                    llm = None
                from src.agents.contract_agents import make_legal_risk_agent, make_mitigation_agent
                chunk_agent = make_legal_risk_agent(llm) if label == "legal_risks" else make_mitigation_agent(llm)
                if label == "legal_risks":
                    t = legal_risk_task(chunk_agent)
                else:
                    t = mitigation_task(chunk_agent)
                t.description = t.description.replace("{contract_text}", chunk_text)
                return t

            results = []
            merged_items: list[dict] = []
            # Parallel execution of chunk tasks
            with ThreadPoolExecutor(max_workers=PAR) as ex:
                fut_map = {ex.submit(_run_single, None, build_chunk_task(c)): idx for idx, c in enumerate(chunks)}
                for fut in as_completed(fut_map):
                    try:
                        results.append(fut.result())
                    except Exception:
                        results.append("[]")

                    # Update partials incrementally with merged arrays so far
                    merged_items = []
                    for r in results:
                        merged_items.extend(_safe_json_list(str(r)))
                    if on_partial:
                        if label == "legal_risks":
                            cur = _merge_risks(merged_items)
                            on_partial(label, {"legal_risks_parsed": cur[:8]})
                        else:
                            # For mitigations we can't fully align until risks ready; still stream best-effort
                            on_partial(label, {"mitigations_parsed": merged_items[:8]})

            # Merge arrays after all chunks complete
            merged_items = []
            for r in results:
                merged_items.extend(_safe_json_list(str(r)))

            if label == "legal_risks":
                merged = _merge_risks(merged_items)
                out = json.dumps(merged, ensure_ascii=False)
                outputs[label] = out
                yield label, out
            else:
                # Use risk clauses for alignment if available
                risk_list = _safe_json_list(outputs.get("legal_risks", "[]"))
                keep_clauses = [r.get("clause", "") for r in risk_list if r.get("clause")]
                merged = _merge_mitigations(merged_items, keep_clauses)
                out = json.dumps(merged, ensure_ascii=False)
                outputs[label] = out
                yield label, out
        elif label == "alert":
            # Derive from risks to avoid another heavy call
            risk_list = _safe_json_list(outputs.get("legal_risks", "[]"))
            out = _alert_from_risks(risk_list)
            outputs[label] = out
            yield label, out
        else:
            # Process entire PDF via chunking for purpose/commercial/plain with parallelism
            CHUNK_CHARS = int(os.getenv("CHUNK_CHARS", "6000"))
            CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "600"))
            chunks = _chunk_text(text, CHUNK_CHARS, CHUNK_OVERLAP)
            env_par = os.getenv("CHUNK_PARALLEL")
            if env_par:
                PAR = max(1, int(env_par))
            else:
                cpu = os.cpu_count() or 2
                PAR = max(2, cpu)
            PAR = min(PAR, max(1, len(chunks)))

            def build_light_chunk_task(chunk_text: str):
                # fresh agent per chunk
                if 'LLM' in globals() and LLM:
                    llm = LLM(model=enforced_model)
                else:
                    llm = None
                from src.agents.contract_agents import (
                    make_purpose_agent,
                    make_commercial_agent,
                    make_simplifier_agent,
                )
                from src.tasks.contract_tasks import (
                    purpose_task as _p_task,
                    commercial_task as _c_task,
                    simplifier_task as _s_task,
                )
                if label == "purpose":
                    a = make_purpose_agent(llm); t = _p_task(a)
                elif label == "commercial":
                    a = make_commercial_agent(llm); t = _c_task(a)
                else:
                    a = make_simplifier_agent(llm); t = _s_task(a)
                t.description = t.description.replace("{contract_text}", chunk_text)
                return a, t

            partials: list[str] = []
            merged_commercial: Dict[str, Any] = {}
            with ThreadPoolExecutor(max_workers=PAR) as ex:
                fut_map = {}
                for c in chunks:
                    a, t = build_light_chunk_task(c)
                    fut_map[ex.submit(_run_single, a, t)] = True
                for fut in as_completed(fut_map):
                    try:
                        partials.append(fut.result())
                    except Exception:
                        partials.append("")

                    # Stream partials as they arrive
                    if on_partial:
                        if label == "commercial":
                            # Incrementally merge JSON objects
                            obj = {}
                            try:
                                obj = json.loads(partials[-1])
                            except Exception:
                                from src.utils.json_sanitizer import extract_json_object
                                obj = extract_json_object(str(partials[-1])) or {}
                            if isinstance(obj, dict):
                                for k, v in obj.items():
                                    if v and k not in merged_commercial:
                                        merged_commercial[k] = v
                            on_partial(label, {"commercial_parsed": merged_commercial})
                        else:
                            # For purpose/plain, stream a quick combined snippet (first 150 words)
                            text_so_far = "\n".join([p for p in partials if isinstance(p, str)])
                            words = text_so_far.split()
                            snippet = " ".join(words[:150])
                            on_partial(label, {label: snippet})

            if label == "commercial":
                # Merge commercial JSON objects over chunks
                try:
                    merged: Dict[str, Any] = {}
                    for p in partials:
                        obj = {}
                        try:
                            obj = json.loads(p)
                        except Exception:
                            from src.utils.json_sanitizer import extract_json_object
                            obj = extract_json_object(str(p)) or {}
                        if isinstance(obj, dict):
                            for k, v in obj.items():
                                if v and k not in merged:
                                    merged[k] = v
                    out = json.dumps(merged, ensure_ascii=False)
                except Exception:
                    out = partials[0] if partials else ""
            else:
                # Combine summaries
                from src.agents.contract_agents import make_purpose_agent, make_simplifier_agent
                agent_factory = make_purpose_agent if label == "purpose" else make_simplifier_agent
                from src.tasks.contract_tasks import purpose_task, simplifier_task
                base_task_factory = purpose_task if label == "purpose" else simplifier_task
                out = _combine_summaries(agent_factory, base_task_factory, partials, title=label)

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


def save_report(result: AnalysisResult, out_dir: Path, contract_name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{contract_name}_analysis.json"
    # Try to parse structured fields
    def _try_json(x):
        try:
            return json.loads(x)
        except Exception:
            return None
    def _bullets(text: str, n=10):
        if not text:
            return []
        lines = [l.strip().lstrip("-*• ") for l in text.splitlines() if l.strip()]
        if lines:
            return lines[:n]
        chunks = [c.strip() for c in text.split(". ") if c.strip()]
        return chunks[:n]

    commercial_parsed = _try_json(result.commercial)
    legal_risks_parsed = _try_json(result.legal_risks)
    mitigations_parsed = _try_json(result.mitigations)
    alert_parsed = _try_json(result.alert)

    report = {
        "summary": {
            "purpose": result.purpose,
            "plain_bullets": _bullets(result.plain, 10),
        },
        "commercial": commercial_parsed if isinstance(commercial_parsed, dict) else result.commercial,
        "legal_risks": legal_risks_parsed if isinstance(legal_risks_parsed, list) else result.legal_risks,
        "mitigations": mitigations_parsed if isinstance(mitigations_parsed, list) else result.mitigations,
        "decision": alert_parsed if isinstance(alert_parsed, dict) else result.alert,
        "meta": {
            "contract": contract_name,
            "model": os.getenv("OLLAMA_MODEL", "ollama/gemma3:1b"),
        }
    }

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
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
