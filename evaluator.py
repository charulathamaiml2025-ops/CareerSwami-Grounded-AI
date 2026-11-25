"""Automated evaluation runner for CareerSwami evaluation-cases.csv."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from assistant import answer_question, get_runtime_config

BACKEND_DIR = Path(__file__).resolve().parent
EVAL_CSV_PATH = BACKEND_DIR / "evaluation-cases.csv"
LATEST_RESULTS_PATH = BACKEND_DIR / "latest_eval_results.json"

CSV_FIELDNAMES = [
    "Test ID",
    "Question",
    "Category",
    "Expected claim IDs",
    "Expected behaviour",
    "Must include",
    "Must not include",
    "Actual response",
    "Pass/Fail",
]


def _parse_pipe_tokens(raw_value: str) -> list[str]:
    """Parse pipe-delimited requirement tokens and unescape escaped dollar signs."""
    if not raw_value or not raw_value.strip():
        return []
    tokens = []
    for part in raw_value.split("|"):
        cleaned = part.strip().replace("\\$", "$")
        if cleaned:
            tokens.append(cleaned)
    return tokens


def _parse_claim_ids(raw_value: str) -> list[str]:
    """Parse comma-separated claim IDs."""
    if not raw_value or not raw_value.strip():
        return []
    return [c.strip().upper() for c in raw_value.split(",") if c.strip()]


def load_evaluation_cases() -> list[dict[str, str]]:
    """Read all test cases from evaluation-cases.csv."""
    with EVAL_CSV_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def _evaluate_single_case(row: dict[str, str]) -> dict[str, Any]:
    """Execute and score a single test case against the live assistant."""
    question = row["Question"]
    expected_claims = _parse_claim_ids(row["Expected claim IDs"])
    expected_behaviour = row["Expected behaviour"].strip().upper()
    must_include = _parse_pipe_tokens(row["Must include"])
    must_not_include = _parse_pipe_tokens(row["Must not include"])

    result = answer_question(question)
    actual_answer = result["answer"]
    actual_status = result["status"].strip().upper()
    actual_claims = [c.upper() for c in result["cited_claims"]]
    answer_lower = actual_answer.lower()

    reasons: list[str] = []

    status_match = actual_status == expected_behaviour
    if not status_match:
        reasons.append(f"Expected status '{expected_behaviour}' but got '{actual_status}'")

    missing_claims = [cid for cid in expected_claims if cid not in actual_claims]
    citation_match = len(missing_claims) == 0
    if not citation_match:
        reasons.append(f"Missing expected claim IDs: {', '.join(missing_claims)}")

    missing_tokens = [tok for tok in must_include if tok.lower() not in answer_lower]
    if missing_tokens:
        reasons.append(f"Missing required text: {', '.join(missing_tokens)}")

    forbidden_hits = [tok for tok in must_not_include if tok.lower() in answer_lower]
    if forbidden_hits:
        reasons.append(f"Contains forbidden text: {', '.join(forbidden_hits)}")

    passed = status_match and citation_match and not missing_tokens and not forbidden_hits

    return {
        "test_id": row["Test ID"],
        "question": question,
        "category": row["Category"],
        "expected_claim_ids": expected_claims,
        "expected_behaviour": expected_behaviour,
        "actual_behaviour": actual_status,
        "actual_claims": actual_claims,
        "actual_response": actual_answer,
        "must_include": must_include,
        "must_not_include": must_not_include,
        "passed": passed,
        "status": "PASS" if passed else "FAIL",
        "citation_match": citation_match,
        "failure_reasons": reasons,
        "mode": result["mode"],
        "model": result["model"],
        "prompt_version": result["prompt_version"],
    }


def _compute_metrics(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute overall and category-level evaluation metrics."""
    total = len(case_results)
    passed = sum(1 for r in case_results if r["passed"])
    failed = total - passed
    accuracy_pct = round((passed / total) * 100, 1) if total else 0.0

    categories: dict[str, dict[str, Any]] = {}
    for item in case_results:
        cat = item["category"]
        bucket = categories.setdefault(cat, {"category": cat, "total": 0, "passed": 0, "failed": 0})
        bucket["total"] += 1
        if item["passed"]:
            bucket["passed"] += 1
        else:
            bucket["failed"] += 1

    for bucket in categories.values():
        bucket["accuracy_pct"] = round((bucket["passed"] / bucket["total"]) * 100, 1) if bucket["total"] else 0.0

    def _cat_pct(name: str) -> float:
        b = categories.get(name)
        return b["accuracy_pct"] if b else 0.0

    citation_ok = sum(1 for r in case_results if r["citation_match"])
    citation_pct = round((citation_ok / total) * 100, 1) if total else 0.0

    refusal_cases = [r for r in case_results if r["category"] in ("Not Covered", "Partially Covered")]
    refusal_ok = sum(1 for r in refusal_cases if r["passed"])
    refusal_pct = round((refusal_ok / len(refusal_cases)) * 100, 1) if refusal_cases else 0.0

    not_covered_count = sum(1 for r in case_results if r["category"] == "Not Covered")
    not_covered_share = round((not_covered_count / total) * 100, 1) if total else 0.0

    cfg = get_runtime_config()
    return {
        "has_run": True,
        "last_run_at": datetime.now(timezone.utc).isoformat(),
        "mode": cfg["mode"],
        "model": cfg["model"],
        "prompt_version": cfg["prompt_version"],
        "total_cases": total,
        "passed": passed,
        "failed": failed,
        "accuracy_pct": accuracy_pct,
        "not_covered_count": not_covered_count,
        "not_covered_share_pct": not_covered_share,
        "grounding_performance_pct": _cat_pct("Directly Answerable"),
        "citation_performance_pct": citation_pct,
        "refusal_performance_pct": refusal_pct,
        "adversarial_resistance_pct": _cat_pct("Adversarial"),
        "category_performance": list(categories.values()),
        "results": case_results,
    }


def run_evaluation_suite() -> dict[str, Any]:
    """Execute all cases in evaluation-cases.csv, persist results, and return report."""
    rows = load_evaluation_cases()
    case_results = [_evaluate_single_case(row) for row in rows]
    report = _compute_metrics(case_results)

    # Persist actual responses and Pass/Fail back to evaluation-cases.csv
    by_id = {r["test_id"]: r for r in case_results}
    updated_rows: list[dict[str, str]] = []
    for row in rows:
        res = by_id[row["Test ID"]]
        row_copy = {k: row.get(k, "") for k in CSV_FIELDNAMES}
        row_copy["Actual response"] = res["actual_response"]
        row_copy["Pass/Fail"] = res["status"]
        updated_rows.append(row_copy)

    import io
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDNAMES, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(updated_rows)
    EVAL_CSV_PATH.write_bytes(buf.getvalue().encode("utf-8"))

    LATEST_RESULTS_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def get_latest_evaluation_report() -> dict[str, Any]:
    """Return latest persisted evaluation report, or un-run state from CSV."""
    if LATEST_RESULTS_PATH.exists():
        return json.loads(LATEST_RESULTS_PATH.read_text(encoding="utf-8"))

    rows = load_evaluation_cases()
    cfg = get_runtime_config()
    not_covered_count = sum(1 for r in rows if r["Category"] == "Not Covered")
    total = len(rows)
    return {
        "has_run": False,
        "last_run_at": None,
        "mode": cfg["mode"],
        "model": cfg["model"],
        "prompt_version": cfg["prompt_version"],
        "total_cases": total,
        "passed": 0,
        "failed": 0,
        "accuracy_pct": None,
        "not_covered_count": not_covered_count,
        "not_covered_share_pct": round((not_covered_count / total) * 100, 1) if total else 0.0,
        "grounding_performance_pct": None,
        "citation_performance_pct": None,
        "refusal_performance_pct": None,
        "adversarial_resistance_pct": None,
        "category_performance": [],
        "results": [
            {
                "test_id": row["Test ID"],
                "question": row["Question"],
                "category": row["Category"],
                "expected_claim_ids": _parse_claim_ids(row["Expected claim IDs"]),
                "expected_behaviour": row["Expected behaviour"],
                "actual_behaviour": "PENDING",
                "actual_claims": [],
                "actual_response": row.get("Actual response", ""),
                "must_include": _parse_pipe_tokens(row["Must include"]),
                "must_not_include": _parse_pipe_tokens(row["Must not include"]),
                "passed": None,
                "status": row.get("Pass/Fail", "PENDING") or "PENDING",
                "citation_match": None,
                "failure_reasons": [],
            }
            for row in rows
        ],
    }
