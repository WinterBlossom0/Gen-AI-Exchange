from __future__ import annotations

from crewai import Agent
from typing import Optional
try:
    # CrewAI provides an LLM wrapper
    from crewai import LLM  # type: ignore
except Exception:  # pragma: no cover - editor helper type
    class LLM:  # type: ignore
        def __init__(self, model: Optional[str] = None):
            self.model = model


def _configure_llm(llm: Optional[LLM]) -> Optional[LLM]:
    """Attach deterministic, high-output settings and Gemini-specific controls when available.
    Avoid broad exception handling; check attributes explicitly.
    """
    if llm is None:
        return None
    import os

    def _get_float(name: str, default: float) -> float:
        val = os.getenv(name)
        if val is None:
            return default
        try:
            return float(val)
        except ValueError:
            return default

    def _get_int(name: str, default: int) -> int:
        val = os.getenv(name)
        if val is None:
            return default
        try:
            return int(val)
        except ValueError:
            return default

    temp = _get_float("GENAI_TEMPERATURE", 0.0)
    top_p = _get_float("GENAI_TOP_P", 0.95)
    token_limit = _get_int("MAX_OUTPUT_TOKENS", 10000000)
    thinking_budget = _get_int("GEMINI_THINKING_BUDGET", 0)

    # Common top-level knobs
    setattr(llm, "temperature", temp)
    setattr(llm, "top_p", top_p)
    setattr(llm, "max_tokens", token_limit)

    # Provider-specific extras
    cfg = {"thinking_budget": thinking_budget}
    if hasattr(llm, "additional_kwargs") and isinstance(getattr(llm, "additional_kwargs"), dict):
        ak = llm.additional_kwargs  # type: ignore[attr-defined]
        ak.setdefault("thinking_config", cfg)
        ak.setdefault("max_output_tokens", token_limit)
        ak.setdefault("max_tokens", token_limit)
        ak.setdefault("safety_settings", [
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "OFF"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "OFF"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "OFF"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "OFF"},
        ])
    elif hasattr(llm, "params") and isinstance(getattr(llm, "params"), dict):
        prm = llm.params  # type: ignore[attr-defined]
        prm.setdefault("thinking_config", cfg)
        prm.setdefault("max_output_tokens", token_limit)
        prm.setdefault("max_tokens", token_limit)
        prm.setdefault("safety_settings", [
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "OFF"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "OFF"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "OFF"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "OFF"},
        ])
    else:
        # Minimal signal for clients that read it
        setattr(llm, "thinking_config", cfg)
    return llm


def make_purpose_agent(llm: Optional[LLM] = None) -> Agent:
    llm = _configure_llm(llm)
    # Encourage JSON object output
    schema = {
        "type": "object",
        "properties": {"summary": {"type": "string"}},
        "required": ["summary"],
    }
    if llm is not None and hasattr(llm, "additional_kwargs") and isinstance(getattr(llm, "additional_kwargs"), dict):
        llm.additional_kwargs.setdefault("response_mime_type", "application/json")
        llm.additional_kwargs.setdefault("response_schema", schema)
    return Agent(
        role="Contract Purpose Analyst",
        goal="Summarize the contract's primary purpose and scope.",
        backstory=(
            "You are a senior commercial analyst experienced in quickly understanding the intent "
            "and scope of agreements such as Master Service Agreements and Statements of Work."
        ),
        verbose=False,
        llm=llm,
    )


def make_commercial_agent(llm: Optional[LLM] = None) -> Agent:
    llm = _configure_llm(llm)
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"clause": {"type": "string"}, "summary": {"type": "string"}},
            "required": ["clause", "summary"],
        },
    }
    if llm is not None and hasattr(llm, "additional_kwargs") and isinstance(getattr(llm, "additional_kwargs"), dict):
        llm.additional_kwargs.setdefault("response_mime_type", "application/json")
        llm.additional_kwargs.setdefault("response_schema", schema)
    return Agent(
        role="Commercial Clauses Analyst",
        goal="Extract and structure all commercial clauses from the contract into a clear, itemized JSON format.",
        backstory=(
            "You specialize in commercial terms: pricing, payment schedules, invoicing, delivery quantities, "
            "and obligations allocation between buyer and supplier."
        ),
        verbose=False,
        llm=llm,
    )


def make_legal_risk_agent(llm: Optional[LLM] = None) -> Agent:
    llm = _configure_llm(llm)
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "clause": {"type": "string"},
                "risk": {"type": "string"},
                "description": {"type": "string"},
                "fairness": {"type": "string", "enum": ["fair", "unfair"]},
                "favours": {"type": "string", "enum": ["buyer", "supplier", "equal"]},
                "severity": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["clause", "risk", "description", "fairness", "favours", "severity"],
        },
    }
    if llm is not None and hasattr(llm, "additional_kwargs") and isinstance(getattr(llm, "additional_kwargs"), dict):
        llm.additional_kwargs.setdefault("response_mime_type", "application/json")
        llm.additional_kwargs.setdefault("response_schema", schema)
    return Agent(
        role="Legal Risk Assessor",
        goal="Identify and assess all potential legal risks in the contract, structuring them in a clear JSON format.",
        backstory=(
            "You are a legal analyst trained to detect imbalanced indemnities, unlimited liability, "
            "broad termination rights, IP ownership traps, and restrictive penalties."
        ),
        verbose=False,
        llm=llm,
    )


def make_mitigation_agent(llm: Optional[LLM] = None) -> Agent:
    llm = _configure_llm(llm)
    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "clause": {"type": "string"},
                "mitigation": {"type": "string"},
                "negotiation_points": {"type": "string"},
            },
            "required": ["clause", "mitigation"],
        },
    }
    if llm is not None and hasattr(llm, "additional_kwargs") and isinstance(getattr(llm, "additional_kwargs"), dict):
        llm.additional_kwargs.setdefault("response_mime_type", "application/json")
        llm.additional_kwargs.setdefault("response_schema", schema)
    return Agent(
        role="Mitigation Strategist",
        goal="Propose practical mitigations for identified risks, structuring them in a clear JSON format.",
        backstory=(
            "You craft practical, negotiable mitigations aligned with industry norms to reduce exposure "
            "while preserving deal viability."
        ),
        verbose=False,
        llm=llm,
    )


def make_alert_agent(llm: Optional[LLM] = None) -> Agent:
    llm = _configure_llm(llm)
    schema = {
        "type": "object",
        "properties": {
            "exploitative": {"type": "boolean"},
            "rationale": {"type": "string"},
            "top_unfair_clauses": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["exploitative", "rationale", "top_unfair_clauses"],
    }
    if llm is not None and hasattr(llm, "additional_kwargs") and isinstance(getattr(llm, "additional_kwargs"), dict):
        llm.additional_kwargs.setdefault("response_mime_type", "application/json")
        llm.additional_kwargs.setdefault("response_schema", schema)
    return Agent(
        role="Exploitative Contract Detector",
        goal=(
            "Decide if the contract is exploitative based on severity and count of unfair clauses. "
            "Return a boolean and rationale."
        ),
        backstory=(
            "You aggregate risk signals and determine whether the overall terms are exploitative enough "
            "to warrant escalation."
        ),
        verbose=False,
        llm=llm,
    )


def make_simplifier_agent(llm: Optional[LLM] = None) -> Agent:
    llm = _configure_llm(llm)
    return Agent(
        role="Plain-Language Simplifier",
        goal=(
            "Explain the contract like I'm not a lawyer. Use simple language, short bullets, and concrete examples. "
            "Avoid jargon; where needed, define it briefly."
        ),
        backstory=(
            "You translate complex legal terms into everyday language for non-experts to make informed decisions."
        ),
        verbose=False,
        llm=llm,
    )


def make_chat_agent(llm: Optional[LLM] = None) -> Agent:
    llm = _configure_llm(llm)
    return Agent(
        role="Contract Q&A Assistant",
        goal=(
            "Answer user questions about the provided contract accurately and concisely, referencing relevant clauses."
        ),
        backstory=(
            "You are a helpful assistant that uses the contract text and analysis summaries to provide clear, practical answers."
        ),
        verbose=False,
        llm=llm,
    )
