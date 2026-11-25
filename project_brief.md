# Project Brief: CareerSwami – Grounded AI Assistant

**Tagline:** *"Answers You Can Trust. No Guesswork. No Hallucinations."*

## 1. Problem Statement
Conventional AI assistants are optimized to sound helpful even when their context lacks the answer, frequently fabricating dates, fees, contact details, or policies. For a student club, hallucinated policies (e.g., promising certificates, guaranteed waitlist spots, or job placement assistance) create operational confusion and erode trust.

## 2. Project Objective
CareerSwami is a grounded AI handbook assistant for a fictional student club designed around **strict epistemic discipline**:
- Answer questions **only** using the official `handbook.txt` and numbered source claims (`C01`–`C11`).
- Cite exact claim IDs (`[C01]`, `[C02]`, ...) for every factual assertion.
- Refuse to speculate or invent facts when information is absent (certificates, session recordings, refund policies, job placement assistance, coordinator personal details).
- Separate supported facts from missing information on partially covered questions.
- Politely refute false user premises in adversarial prompts using handbook evidence.
- Direct users to **the club coordinator** whenever information is missing or requires clarification.

## 3. Scope & Core Constraints
- **Single Source of Truth:** `backend/handbook.txt` (11 atomic facts) mapped to `backend/source_claims.json` (`C01`–`C11`).
- **Four Answer Categories:**
  1. `GROUNDED ANSWER` (Directly Answerable)
  2. `NOT COVERED` (Missing Policy / Refusal)
  3. `PARTIALLY COVERED` (Fact + Missing Policy Separation)
  4. `FALSE PREMISE CORRECTED` (Adversarial Resistance)
- **Dual Execution Mode:** Configurable LLM integration (via environment variable) paired with a deterministic, rule-based grounded fallback engine so the full system runs reliably offline or without paid API keys.

## 4. Deliverables
1. Full-stack React (Vite + Tailwind CSS) + FastAPI web application with 5 pages: Dashboard, AI Handbook Assistant, Handbook Explorer, Evaluation Dashboard, and Project Documentation.
2. Versioned system prompt (`prompts/system_prompt_v1.txt`) and prompt iteration log (`prompts/prompt_version_log.md`).
3. Evaluation dataset (`backend/evaluation-cases.csv`) with 28 test cases (including >25% uncovered questions) and live automated runner.
4. Evidence log, test results, quality criteria, source table, and setup README.
