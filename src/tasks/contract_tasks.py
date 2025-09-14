from __future__ import annotations

from crewai import Task

PURPOSE_PROMPT = (
    "Summarize the contract for a busy reader in 2–3 short sentences: what it’s for, the scope, and the main deliverables. "
    "Be direct and concrete. Keep it under 80 words.\n\nContract:\n{contract_text}"
)

COMMERCIAL_PROMPT = (
    "List the core commercial terms as a compact JSON object with these keys: payment_terms, pricing_model, quantities, buyer_obligations, supplier_obligations. "
    "Keep values brief (≤200 chars). If something isn’t stated, use an empty string ''. Reply with JSON only—no extra words.\n\nContract:\n{contract_text}"
)

LEGAL_RISK_PROMPT = (
    "Identify up to 8 important legal risks. Return a JSON array only. Each item: {clause: string≤180, risk: string≤180, fairness: fair|unfair, favours: buyer|supplier|equal, severity: low|medium|high}.\n\n"
    "Contract:\n{contract_text}"
)

MITIGATION_PROMPT = (
    "Suggest practical mitigations matching the key risks (same order). Return JSON array only. Each item: {clause: string≤120, mitigation: string≤180, negotiation_points: string≤180}.\n\n"
    "Contract:\n{contract_text}"
)

ALERT_PROMPT = (
    "Based on the risk profile, decide if this contract is exploitative overall. Keep the reasoning short. "
    "Return JSON only: {exploitative: true|false, rationale: string≤240, top_unfair_clauses: string[]}\n\nContract:\n{contract_text}"
)

SIMPLIFIER_PROMPT = (
    "Explain this contract so anyone can understand it without losing key legal meaning. "
    "Use very simple words and short lines. If a legal term appears, add a plain meaning in brackets (e.g., indemnity [who pays for harm]). "
    "Write 8–10 bullets, each ≤140 characters. Start lines with You:, They:, or Both:. Include things like purpose, duties, money, deadlines, changes, IP, confidentiality, limits on damages, indemnity, termination, law/court, late fees, privacy, warranties, acceptance/tests. "
    "Finish with 1–2 Watch out: lines for the biggest risks. No intro/outro.\n\nContract:\n{contract_text}"
)

CHAT_PROMPT = (
    "Answer the question strictly from the contract. If something isn’t stated, say: Not stated in the contract.\n"
    "Format:\n"
    "- Direct answer first (≤20 words). If yes/no, start with Yes. or No.\n"
    "- Then a short reason with clause ref(s) in parentheses, e.g., (Clause 5, Termination).\n"
    "- If multiple parts, label A), B). Keep total under 100 words.\n\n"
    "Contract:\n{contract_text}\n\nAnalysis:\n{analysis}\n\nQuestion:\n{question}"
)


def purpose_task(agent) -> Task:
    return Task(description=PURPOSE_PROMPT, agent=agent, expected_output="3-6 sentence summary")


def commercial_task(agent) -> Task:
    return Task(description=COMMERCIAL_PROMPT, agent=agent, expected_output="Strict JSON object for commercial terms")


def legal_risk_task(agent) -> Task:
    return Task(description=LEGAL_RISK_PROMPT, agent=agent, expected_output="Strict JSON array of risks (<=8)")


def mitigation_task(agent) -> Task:
    return Task(description=MITIGATION_PROMPT, agent=agent, expected_output="Strict JSON array of mitigations")


def alert_task(agent) -> Task:
    return Task(description=ALERT_PROMPT, agent=agent, expected_output="Strict JSON decision object")


def simplifier_task(agent) -> Task:
    return Task(description=SIMPLIFIER_PROMPT, agent=agent, expected_output="Max 8 short bullets")


def chat_task(agent, contract_text: str, analysis: str, question: str) -> Task:
    prompt = CHAT_PROMPT.format(contract_text=contract_text, analysis=analysis, question=question)
    return Task(description=prompt, agent=agent, expected_output="Helpful, accurate answer with clause references")
