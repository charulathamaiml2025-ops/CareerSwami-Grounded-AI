# Prompt Version Log

| Version | Date | Author | Summary of Changes | Status |
| :--- | :--- | :--- | :--- | :--- |
| `v1.0` | 2026-11-25 | CareerSwami Engineering | Initial grounded system prompt incorporating the 5-step factual verification workflow, explicit refusal instructions for uncovered topics (certificates, recordings, refunds, job placements), partial-coverage separation, adversarial premise correction, strict coordinator identity guard ("the club coordinator" only), and structured JSON output schema (`status`, `answer`, `cited_claims`, `missing_information`). | Active |

## Design Rationale (`v1.0`)
1. **Priority Inversion:** Explicitly instructs *"Your priority is factual reliability, not answering every question"* to counteract standard RLHF helpfulness bias that causes hallucinations.
2. **Topic-Specific Guardrails:** Explicitly enumerates certificates, recordings, refunds, and job placement so borderline queries (e.g., "If there are no fees, what is the refund process?") do not extrapolate "no fees" into a fabricated refund policy.
3. **Structured Output:** Enforces explicit status classification (`GROUNDED ANSWER`, `PARTIALLY COVERED`, `NOT COVERED`, `FALSE PREMISE CORRECTED`) and explicit `cited_claims` arrays so the frontend and automated evaluator can verify citations deterministically.
