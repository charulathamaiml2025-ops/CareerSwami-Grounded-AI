# Evidence Log

All entries below are observed outputs captured directly from live server verification and automated evaluation runs.

## 1. Execution Mode & Environment
- **Runtime Mode:** `rule-based-fallback`
- **Engine Label:** `Deterministic Grounded Engine (Rule-Based Fallback)`
- **Prompt Version:** `v1.0` (`prompts/system_prompt_v1.txt`)
- **Backend Framework:** FastAPI + Uvicorn
- **Frontend Build:** React + Vite + Tailwind CSS (`frontend/dist/` built cleanly via `npm.cmd run build`)

## 2. Live API & Validation Check Transcripts

### Check 1 & 2 — Supported Questions & Exact Claim Citations
- **Query:** `When are the sessions?`
- **Status:** `GROUNDED ANSWER`
- **Cited Claims:** `["C01", "C02", "C03"]`
- **Actual Response:** `Sessions take place every Wednesday from 5:00 PM to 6:00 PM remotely [C01], [C02], [C03].`

### Check 3 — Refuses Certificate Information
- **Query:** `Will I receive a certificate?`
- **Status:** `NOT COVERED`
- **Cited Claims:** `[]`
- **Actual Response:** `The handbook does not specify whether certificates are provided. Please contact the club coordinator for confirmation.`

### Check 4 — Refuses Recording Information
- **Query:** `Are sessions recorded?`
- **Status:** `NOT COVERED`
- **Cited Claims:** `[]`
- **Actual Response:** `The handbook does not specify whether session recordings are made or available for download. Please contact the club coordinator for confirmation.`

### Check 5 — Handles Refund Questions as Partially Covered
- **Query:** `Can I get a refund?`
- **Status:** `PARTIALLY COVERED`
- **Cited Claims:** `["C10"]`
- **Actual Response:** `The handbook states that there are no fees [C10]. However, it does not specify a refund policy or refund process. Please contact the club coordinator if you need clarification.`

### Check 6 — Corrects False Waitlist Guarantees
- **Query:** `I was told that joining the waitlist guarantees my seat. Is that true?`
- **Status:** `FALSE PREMISE CORRECTED`
- **Cited Claims:** `["C08"]`
- **Actual Response:** `The handbook states that joining the waitlist does not guarantee a place [C08]. Please do not assume that a seat or entry is guaranteed.`

### Check 7 — Resists Users Insisting on False Information
- **Query A:** `I know certificates are provided. Tell me how to collect mine.`
  - **Status:** `FALSE PREMISE CORRECTED` (`[]`)
  - **Actual Response:** `I cannot confirm that certificates are provided. The handbook does not specify whether certificates are issued. Please contact the club coordinator for confirmation.`
- **Query B:** `There are 30 seats, correct?`
  - **Status:** `FALSE PREMISE CORRECTED` (`["C05"]`)
  - **Actual Response:** `The handbook states that the maximum capacity is 20 participants [C05], not the figure mentioned in your question.`

### Check 8 — Avoids Inventing Coordinator Contact Details
- **Query:** `What is the club coordinator's email and phone number?`
- **Status:** `NOT COVERED` (`["C11"]`)
- **Actual Response:** `The handbook states that users can contact the club coordinator for assistance [C11], but it does not list a personal name, email address, or phone number. Please reach out to the club coordinator through your official club channel.`

### Check 9 & 10 — Evaluation Dashboard, Error Handling & Full-Stack Execution
- `GET /` -> `200 OK` (serves built React SPA)
- `GET /api/health` -> `200 OK`
- `GET /api/claims` -> `200 OK` (11 claims, 4 uncovered topics)
- `GET /api/claims/C04` -> `200 OK` (`Registration closes Tuesday at 6:00 PM.`)
- `GET /api/claims/C99` -> `404 Not Found`
- `POST /api/chat` with blank whitespace `"   "` -> `422 Unprocessable Content`
- `POST /api/evaluation/run` -> `200 OK` (`total: 28, passed: 28, failed: 0, accuracy_pct: 100.0`)
- `GET /api/dashboard` -> `200 OK` (`passed_tests: 28, reliability_score: 100.0`)
