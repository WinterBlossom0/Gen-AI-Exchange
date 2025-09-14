from __future__ import annotations

from crewai import Task

PURPOSE_PROMPT = (
    "You are given a contract. Analyze and summarize: (1) the primary purpose, (2) scope, and (3) key "
    "deliverables/outcomes. Provide a concise 3-6 sentence summary.\n\nContract:\n{contract_text}"
)

COMMERCIAL_PROMPT = (
    "Extract commercial terms and present as JSON with keys: payment_terms, pricing_model, quantities, "
    "buyer_obligations, supplier_obligations. Quote clause snippets where possible.\n\nContract:\n{contract_text}"
)

LEGAL_RISK_PROMPT = (
    "Identify legal risks. For each, produce JSON with fields: clause, risk, fairness (fair/unfair), "
    "favours (buyer/supplier/equal), severity (low/medium/high).\n\nContract:\n{contract_text}"
)

MITIGATION_PROMPT = (
    "Given the identified legal risks, propose concrete mitigations. For each risk, output JSON with: "
    "clause, mitigation, negotiation_points, references (if any).\n\nContract:\n{contract_text}"
)

ALERT_PROMPT = (
    "Decide if the contract is exploitative overall. Consider count and severity of 'unfair' risks. "
    "Return JSON with: exploitative (true/false), rationale, top_unfair_clauses (array).\n\nContract:\n{contract_text}"
)

SIMPLIFIER_PROMPT = (
    "Rewrite the contract in plain language for non-lawyers. Use short bullets and simple sentences. "
    "Include: purpose, key duties for both parties, payment terms, timelines, risks (who they favor), and what to watch out for.\n\n"
    "Contract:\n{contract_text}"
)

CHAT_PROMPT = (
    "You will answer questions about the contract. Base answers strictly on the contract and the analysis.\n\n"
    "Contract:\n{contract_text}\n\nAnalysis:\n{analysis}\n\nQuestion:\n{question}"
)


def purpose_task(agent) -> Task:
    return Task(description=PURPOSE_PROMPT, agent=agent, expected_output="3-6 sentence summary")


def commercial_task(agent) -> Task:
    return Task(description=COMMERCIAL_PROMPT, agent=agent, expected_output="JSON with commercial terms")


def legal_risk_task(agent) -> Task:
    return Task(description=LEGAL_RISK_PROMPT, agent=agent, expected_output="JSON list of risks")


def mitigation_task(agent) -> Task:
    return Task(description=MITIGATION_PROMPT, agent=agent, expected_output="JSON mitigations per risk")


def alert_task(agent) -> Task:
    return Task(description=ALERT_PROMPT, agent=agent, expected_output="JSON exploitative decision")


def simplifier_task(agent) -> Task:
    return Task(description=SIMPLIFIER_PROMPT, agent=agent, expected_output="Plain-language summary")


def chat_task(agent, contract_text: str, analysis: str, question: str) -> Task:
    prompt = CHAT_PROMPT.format(contract_text=contract_text, analysis=analysis, question=question)
    return Task(description=prompt, agent=agent, expected_output="Helpful, accurate answer with clause references")
