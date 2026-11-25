# Evaluation Test Results

## Run Metadata
- **Execution Engine:** `Deterministic Grounded Engine (Rule-Based Fallback)` (`mode: rule-based-fallback`)
- **Note on Model Label:** Executed in deterministic rule-based fallback mode without a paid external LLM API key configured. Not claimed as an external LLM run.
- **Prompt Version:** `v1.0` (`prompts/system_prompt_v1.txt`)
- **Dataset:** `backend/evaluation-cases.csv` (28 test cases; 8 Not Covered = 28.6%)
- **Execution Command:** `POST /api/evaluation/run` (persisted to `backend/evaluation-cases.csv` and `backend/latest_eval_results.json`)

## Summary Metrics
| Metric | Result |
| :--- | :--- |
| **Total Test Cases** | 28 |
| **Passed Tests** | 28 |
| **Failed Tests** | 0 |
| **Overall Accuracy** | 100.0% |
| **Grounding Performance (Directly Answerable)** | 100.0% (9/9) |
| **Citation Performance** | 100.0% (28/28) |
| **Refusal & Separation Performance (Not Covered + Partially Covered)** | 100.0% (12/12) |
| **Adversarial Resistance** | 100.0% (7/7) |

## Iteration History (Bugs Caught & Fixed)
1. **Initial Run (24/28 = 85.7%):**
   - `T10` ("Are sessions recorded?") and `T13` ("Can I download recorded sessions?") triggered the mixed-intent `PARTIALLY COVERED` branch because the generic word `"sessions"` matched schedule claims (`C01`–`C03`).
   - `T14` ("Is there a placement guarantee?") triggered `PARTIALLY COVERED` because `"guarantee"` matched `C08` (waitlist guarantee).
   - `T20` ("My friend said sessions are recorded. Is that correct?") failed a `Must not include` check because the refusal phrasing contained `"whether sessions are recorded"`.
2. **Fix Applied (`backend/assistant.py`):**
   - Restricted the compound partial-coverage branch to queries with explicit compound conjunctions (`and`, `also`, `plus`, `as well as`) and disallowed `C08` matching without `"waitlist"`.
   - Updated the recording refusal wording to `"whether session recordings are available"` / `"whether session recordings are made or available for download"`.
3. **Final Verified Run:** 28/28 Passed (100.0%).

## Complete Case-by-Case Results
| Test ID | Category | Expected Behaviour | Actual Behaviour | Cited Claims | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T01 | Directly Answerable | GROUNDED ANSWER | GROUNDED ANSWER | C01, C02, C03 | PASS |
| T02 | Directly Answerable | GROUNDED ANSWER | GROUNDED ANSWER | C02 | PASS |
| T03 | Directly Answerable | GROUNDED ANSWER | GROUNDED ANSWER | C03 | PASS |
| T04 | Directly Answerable | GROUNDED ANSWER | GROUNDED ANSWER | C04 | PASS |
| T05 | Directly Answerable | GROUNDED ANSWER | GROUNDED ANSWER | C05 | PASS |
| T06 | Directly Answerable | GROUNDED ANSWER | GROUNDED ANSWER | C06 | PASS |
| T07 | Directly Answerable | GROUNDED ANSWER | GROUNDED ANSWER | C07, C08 | PASS |
| T08 | Directly Answerable | GROUNDED ANSWER | GROUNDED ANSWER | C09 | PASS |
| T09 | Not Covered | NOT COVERED | NOT COVERED | — | PASS |
| T10 | Not Covered | NOT COVERED | NOT COVERED | — | PASS |
| T11 | Not Covered | NOT COVERED | NOT COVERED | — | PASS |
| T12 | Not Covered | NOT COVERED | NOT COVERED | — | PASS |
| T13 | Not Covered | NOT COVERED | NOT COVERED | — | PASS |
| T14 | Not Covered | NOT COVERED | NOT COVERED | — | PASS |
| T15 | Partially Covered | PARTIALLY COVERED | PARTIALLY COVERED | C10 | PASS |
| T16 | Partially Covered | PARTIALLY COVERED | PARTIALLY COVERED | C10 | PASS |
| T17 | Partially Covered | PARTIALLY COVERED | PARTIALLY COVERED | C10 | PASS |
| T18 | Partially Covered | PARTIALLY COVERED | PARTIALLY COVERED | C09, C10 | PASS |
| T19 | Adversarial | FALSE PREMISE CORRECTED | FALSE PREMISE CORRECTED | C08 | PASS |
| T20 | Adversarial | FALSE PREMISE CORRECTED | FALSE PREMISE CORRECTED | — | PASS |
| T21 | Adversarial | FALSE PREMISE CORRECTED | FALSE PREMISE CORRECTED | — | PASS |
| T22 | Adversarial | FALSE PREMISE CORRECTED | FALSE PREMISE CORRECTED | C04 | PASS |
| T23 | Adversarial | FALSE PREMISE CORRECTED | FALSE PREMISE CORRECTED | C05 | PASS |
| T24 | Adversarial | FALSE PREMISE CORRECTED | FALSE PREMISE CORRECTED | C06 | PASS |
| T25 | Not Covered | NOT COVERED | NOT COVERED | C11 | PASS |
| T26 | Directly Answerable | GROUNDED ANSWER | GROUNDED ANSWER | C01, C02, C03, C10 | PASS |
| T27 | Not Covered | NOT COVERED | NOT COVERED | — | PASS |
| T28 | Adversarial | FALSE PREMISE CORRECTED | FALSE PREMISE CORRECTED | C08 | PASS |
