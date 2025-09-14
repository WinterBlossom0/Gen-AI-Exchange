from __future__ import annotations

from crewai import Agent
from typing import Optional
try:
    # CrewAI provides an LLM wrapper
    from crewai import LLM  # type: ignore
except Exception:  # pragma: no cover - fallback type for editors
    class LLM:  # type: ignore
        def __init__(self, model: Optional[str] = None):
            self.model = model


def make_purpose_agent(llm: Optional[LLM] = None) -> Agent:
    return Agent(
        role="Contract Purpose Analyst",
        goal=(
            "Identify and summarize the primary purpose, scope, and deliverables of the contract "
            "in 3-6 sentences."
        ),
        backstory=(
            "You are a senior commercial analyst experienced in quickly understanding the intent "
            "and scope of agreements such as Master Service Agreements and Statements of Work."
        ),
        verbose=True,
        llm=llm,
    )


def make_commercial_agent(llm: Optional[LLM] = None) -> Agent:
    return Agent(
        role="Commercial Clauses Analyst",
        goal=(
            "Extract payment terms, pricing model, quantities/volumes, and obligations of both parties. "
            "Return a structured summary indicating clauses for both parties."
        ),
        backstory=(
            "You specialize in commercial terms: pricing, payment schedules, invoicing, delivery quantities, "
            "and obligations allocation between buyer and supplier."
        ),
        verbose=True,
        llm=llm,
    )


def make_legal_risk_agent(llm: Optional[LLM] = None) -> Agent:
    return Agent(
        role="Legal Risk Assessor",
        goal=(
            "Identify potentially unfair clauses and whether they favor one party or are balanced. "
            "Label each as unfair/fair and note which party benefits, if applicable."
        ),
        backstory=(
            "You are a legal analyst trained to detect imbalanced indemnities, unlimited liability, "
            "broad termination rights, IP ownership traps, and restrictive penalties."
        ),
        verbose=True,
        llm=llm,
    )


def make_mitigation_agent(llm: Optional[LLM] = None) -> Agent:
    return Agent(
        role="Mitigation Strategist",
        goal=(
            "Propose mitigations to the identified legal risks, including reasonable penalty structures, "
            "cure periods, caps on liability, and jurisdiction/forum choices."
        ),
        backstory=(
            "You craft practical, negotiable mitigations aligned with industry norms to reduce exposure "
            "while preserving deal viability."
        ),
        verbose=True,
        llm=llm,
    )


def make_alert_agent(llm: Optional[LLM] = None) -> Agent:
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
        verbose=True,
        llm=llm,
    )


def make_simplifier_agent(llm: Optional[LLM] = None) -> Agent:
    return Agent(
        role="Plain-Language Simplifier",
        goal=(
            "Explain the contract like I'm not a lawyer. Use simple language, short bullets, and concrete examples. "
            "Avoid jargon; where needed, define it briefly."
        ),
        backstory=(
            "You translate complex legal terms into everyday language for non-experts to make informed decisions."
        ),
        verbose=True,
        llm=llm,
    )


def make_chat_agent(llm: Optional[LLM] = None) -> Agent:
    return Agent(
        role="Contract Q&A Assistant",
        goal=(
            "Answer user questions about the provided contract accurately and concisely, referencing relevant clauses."
        ),
        backstory=(
            "You are a helpful assistant that uses the contract text and analysis summaries to provide clear, practical answers."
        ),
        verbose=True,
        llm=llm,
    )
