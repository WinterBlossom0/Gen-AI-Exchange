from __future__ import annotations

from crewai import Task

PURPOSE_PROMPT = (
    "Return a JSON object with a single 'summary' field containing a 3-6 sentence summary of the contract's primary purpose, scope, and deliverables. "
    "Example: {\"summary\": \"This contract establishes...\"}. "
    "Do not include any other text outside the JSON object."
    "\n\nContract:\n{contract_text}"
)

COMMERCIAL_PROMPT = (
    "Extract commercial clauses only. Return JSON array only (no prose).\n"
    "Each item must have at least: {\"clause\": \"title or section name\", \"summary\": \"what it specifies\"}.\n"
    "Optional fields you may include when present: amounts, currency, dates, parties, obligations, payment_terms, pricing_model, quantities.\n"
    "MANDATORY: Return 5–15 items. Do NOT return an empty array. Use exact figures/dates from the contract where available.\n\n"
    "Contract:\n{contract_text}"
)

LEGAL_RISK_PROMPT = (
    "MANDATORY: Identify at least 3-8 legal risks from this contract. Even if terms seem balanced, analyze potential risks. "
    "Return a JSON array only. Each item must have: {\"clause\": \"specific clause/section\", \"risk\": \"what could go wrong\", \"description\": \"why this is a legal risk (cite clause language)\", \"fairness\": \"fair|unfair\", \"favours\": \"buyer|supplier|equal\", \"severity\": \"low|medium|high\"}.\n\n"
    "Focus on: liability, indemnification, termination, IP ownership, payment terms, warranties, force majeure, governing law, dispute resolution.\n"
    "Do NOT return an empty array. If contract seems simple, identify at least basic risks like payment delays, termination conditions, etc.\n\n"
    "Strictly output JSON only inside a single ```json fenced block. No prose, no markdown outside the fence.\n\n"
    "Contract:\n{contract_text}"
)

MITIGATION_PROMPT = (
    "MANDATORY: Suggest at least 3-8 practical mitigations for contract risks. Return JSON array only. "
    "Each item must have: {\"clause\": \"clause/section being addressed\", \"mitigation\": \"specific action to reduce risk\", \"negotiation_points\": \"what to negotiate\"}.\n\n"
    "Focus on common mitigations: liability caps, termination notice periods, IP protections, payment security, warranty limits, dispute procedures.\n"
    "Do NOT return an empty array. Even for simple contracts, suggest basic protections.\n\n"
    "Contract:\n{contract_text}"
)

ALERT_PROMPT = (
    "Based on the risk profile, decide if this contract is exploitative overall. Keep the reasoning short. "
    "Return JSON only: {exploitative: true|false, rationale: string≤240, top_unfair_clauses: string[]}\n\nContract:\n{contract_text}"
)

SIMPLIFIER_PROMPT = (
    "Explain this specific contract in bullet points only, based strictly on the contract text. Do NOT define what a contract is. "
    "Keep legal nuances intact: do not oversimplify; include what each clause does and why it matters. "
    "If a legal term appears, add a plain meaning in brackets (e.g., indemnity [who pays for harm]). "
    "Requirements:\n"
    "- 10–14 bullets; length per bullet can be longer if needed to preserve nuance.\n"
    "- Start each line with You:, They:, Both:, or Watch out:.\n"
    "- Use exact party names and figures/dates from the contract when present.\n"
    "- If something isn’t stated, write 'Not stated'.\n"
    "- No intro/outro. No headings. No 'Answer' text.\n\n"
    "Contract:\n{contract_text}"
)

CHAT_PROMPT = (
    "Answer strictly from the contract. If not stated, reply: Not stated in the contract.\n"
    "Rules:\n"
    "- Line 1: Direct answer (≤20 words). If yes/no, start with Yes. or No. No markdown, no headings.\n"
    "- Line 2: Reason with clause ref(s) in parentheses, e.g., (Clause 5, Termination).\n"
    "- Optional Line 3: B) if the question has distinct parts.\n"
    "- Keep total under 100 words. No 'Final Answer', no banners, no markdown.\n\n"
    "Contract:\n{contract_text}\n\nAnalysis:\n{analysis}\n\nQuestion:\n{question}"
)


def purpose_task(agent) -> Task:
    return Task(description=PURPOSE_PROMPT, agent=agent, expected_output="3-6 sentence summary")


def commercial_task(agent) -> Task:
    return Task(description=COMMERCIAL_PROMPT, agent=agent, expected_output="Strict JSON array of commercial clause objects")


def legal_risk_task(agent) -> Task:
    return Task(description=LEGAL_RISK_PROMPT, agent=agent, expected_output="Strict JSON array of risks (<=8)")


def mitigation_task(agent) -> Task:
    return Task(description=MITIGATION_PROMPT, agent=agent, expected_output="Strict JSON array of mitigations")


def alert_task(agent) -> Task:
    return Task(description=ALERT_PROMPT, agent=agent, expected_output="Strict JSON decision object")


def simplifier_task(agent) -> Task:
    return Task(description=SIMPLIFIER_PROMPT, agent=agent, expected_output="Thorough plain-language bullets preserving nuance")


def chat_task(agent, contract_text: str, analysis: str, question: str) -> Task:
    prompt = CHAT_PROMPT.format(contract_text=contract_text, analysis=analysis, question=question)
    return Task(description=prompt, agent=agent, expected_output="Helpful, accurate answer with clause references")
