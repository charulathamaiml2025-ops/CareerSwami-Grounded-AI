"""FastAPI server for CareerSwami – Grounded AI Handbook Assistant."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from assistant import answer_question, get_runtime_config, load_system_prompt
from evaluator import get_latest_evaluation_report, run_evaluation_suite
from retrieval import get_claim_by_id, load_claims_data, load_handbook

PROJECT_ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="CareerSwami – Grounded AI Assistant API",
    description="Strictly handbook-grounded student club assistant with live evaluation API.",
    version="1.0.0",
)

raw_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
)
allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    """Validated user chat prompt."""

    question: str = Field(..., min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def strip_and_validate(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question cannot be blank.")
        return cleaned


@app.get("/api/health")
def health_check() -> dict[str, Any]:
    """Return service health and active assistant mode."""
    cfg = get_runtime_config()
    return {
        "status": "ok",
        "service": "CareerSwami Grounded AI Assistant",
        **cfg,
    }


@app.get("/api/dashboard")
def get_dashboard_summary() -> dict[str, Any]:
    """Aggregate overview metrics for the Dashboard page."""
    claims_data = load_claims_data()
    eval_report = get_latest_evaluation_report()
    cfg = get_runtime_config()
    return {
        "project_title": "CareerSwami – Grounded AI Assistant",
        "tagline": "Answers You Can Trust. No Guesswork. No Hallucinations.",
        "description": (
            "An evidence-backed AI handbook assistant for a student club that answers strictly "
            "from verified handbook claims, cites exact sources, resists false premises, and "
            "refuses to guess when policies are not documented."
        ),
        "total_claims": len(claims_data["claims"]),
        "uncovered_topics_count": len(claims_data.get("uncovered_topics", [])),
        "total_tests": eval_report["total_cases"],
        "passed_tests": eval_report["passed"],
        "failed_tests": eval_report["failed"],
        "reliability_score": eval_report["accuracy_pct"],
        "has_eval_run": eval_report["has_run"],
        "last_eval_at": eval_report["last_run_at"],
        "mode": cfg["mode"],
        "model": cfg["model"],
        "prompt_version": cfg["prompt_version"],
    }


@app.get("/api/claims")
def list_claims() -> dict[str, Any]:
    """Return all official claims, uncovered topics, and the raw handbook."""
    data = load_claims_data()
    return {
        "handbook_title": data["handbook_title"],
        "handbook_version": data["handbook_version"],
        "handbook_text": load_handbook(),
        "claims": data["claims"],
        "uncovered_topics": data.get("uncovered_topics", []),
    }


@app.get("/api/claims/{claim_id}")
def read_claim(claim_id: str) -> dict[str, Any]:
    """Retrieve details for a single numbered source claim."""
    claim = get_claim_by_id(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found.")
    return claim


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    """Answer a user question strictly grounded in the official handbook."""
    return answer_question(request.question)


@app.get("/api/evaluation")
def get_evaluation() -> dict[str, Any]:
    """Return evaluation test cases and latest persisted metrics."""
    return get_latest_evaluation_report()


@app.post("/api/evaluation/run")
def execute_evaluation() -> dict[str, Any]:
    """Run all evaluation cases against the live assistant and persist results."""
    return run_evaluation_suite()


@app.get("/api/docs-meta")
def get_docs_meta() -> dict[str, Any]:
    """Return active system prompt text and prompt version metadata for documentation page."""
    cfg = get_runtime_config()
    return {
        "prompt_version": cfg["prompt_version"],
        "system_prompt": load_system_prompt(),
        "mode": cfg["mode"],
        "model": cfg["model"],
    }


FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str) -> FileResponse:
        """Serve the built React SPA for non-API routes."""
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found.")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
