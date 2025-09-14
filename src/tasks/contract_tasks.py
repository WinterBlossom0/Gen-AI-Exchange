from __future__ import annotations

from crewai import Task

PURPOSE_PROMPT = (
    "You are given a contract. In 2-3 short sentences MAX, summarize: (1) primary purpose, (2) scope, (3) key deliverables. "
    "Be concrete. No fluff, no preambles. <= 80 words total.\n\nContract:\n{contract_text}"
)

COMMERCIAL_PROMPT = (
    "Extract commercial terms as STRICT JSON. Keys: payment_terms, pricing_model, quantities, buyer_obligations, supplier_obligations. "
    "Each value MUST be short (<= 200 chars). If unknown, use an empty string ''. No extra text.\n\nContract:\n{contract_text}"
)

LEGAL_RISK_PROMPT = (
    "Identify top legal risks (max 8). Output STRICT JSON array. Each item: {clause: string<=180, risk: string<=180, fairness: fair|unfair, favours: buyer|supplier|equal, severity: low|medium|high}. "
    "No extra commentary.\n\nContract:\n{contract_text}"
)

MITIGATION_PROMPT = (
    "Propose mitigations for the key risks (align order with risks). Output STRICT JSON array, items: {clause: string<=120, mitigation: string<=180, negotiation_points: string<=180}. "
    "Be specific and concise.\n\nContract:\n{contract_text}"
)

ALERT_PROMPT = (
    "Decide if the contract is exploitative overall. Consider count and severity of 'unfair' risks. "
    "Return STRICT JSON: {exploitative: true|false, rationale: string<=240, top_unfair_clauses: string[]}\n\nContract:\n{contract_text}"
)

SIMPLIFIER_PROMPT = (
    "Explain the contract so someone with very low literacy can understand without losing legal nuance. "
    "Use very simple words and short phrases. Avoid legal jargon; if a legal term must appear, explain it in brackets, e.g., indemnity (who pays for harm). "
    "OUTPUT: 8-10 bullets, each <= 140 chars. Start bullets with You:, They:, or Both: for clarity. "
    "Cover, if present: purpose; who does what; money (how much, when); time limits; changes/scope; IP ownership; secrets (confidentiality); damage limits (caps); who pays if things go wrong (indemnity); ending early (termination); which law/court; penalties/late fees; data privacy; warranties; acceptance/tests. "
    "End with 1-2 bullets of Watch out: biggest risks to you. No intro or outro.\n\nContract:\n{contract_text}"
)

CHAT_PROMPT = (
    "Answer ONLY the user question using the contract and analysis. Do not invent facts. If not stated, say 'Not stated in the contract.' "
    "Format: \n"
    "- First line: Direct answer (<= 20 words). If yes/no, start with Yes. or No.\n"
    "- Second line: Brief reason with clause reference(s) in parentheses, e.g., (Clause 5, Termination).\n"
    "- If the question has parts, label A), B).\n"
    "Keep total under 100 words.\n\nContract:\n{contract_text}\n\nAnalysis:\n{analysis}\n\nQuestion:\n{question}"
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
