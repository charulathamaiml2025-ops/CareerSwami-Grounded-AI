"""Handbook and source claim retrieval utilities for CareerSwami."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent
HANDBOOK_PATH = BACKEND_DIR / "handbook.txt"
CLAIMS_PATH = BACKEND_DIR / "source_claims.json"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do",
    "does", "for", "from", "get", "have", "how", "i", "if", "in", "is", "it",
    "me", "my", "of", "on", "or", "right", "should", "that", "the", "there",
    "they", "this", "to", "was", "what", "when", "where", "whether", "which",
    "who", "will", "with", "would", "you", "your",
}


def normalize_text(text: str) -> str:
    """Lowercase text and collapse extra whitespace."""
    cleaned = re.sub(r"[^\w\s:$-]", " ", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def tokenize(text: str) -> list[str]:
    """Tokenize text into meaningful words for retrieval."""
    tokens = re.findall(r"[a-z0-9:]+", text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def load_handbook() -> str:
    """Read the official handbook text."""
    return HANDBOOK_PATH.read_text(encoding="utf-8")


def load_claims_data() -> dict[str, Any]:
    """Load the structured source_claims.json payload."""
    return json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))


def get_claims_map() -> dict[str, dict[str, Any]]:
    """Return a dict mapping claim_id -> claim metadata."""
    data = load_claims_data()
    return {claim["claim_id"]: claim for claim in data["claims"]}


def get_claim_by_id(claim_id: str) -> dict[str, Any] | None:
    """Fetch a single claim by its ID (case-insensitive)."""
    return get_claims_map().get(claim_id.upper())


def retrieve_relevant_claims(query: str, min_score: float = 0.8) -> list[dict[str, Any]]:
    """Score and return source claims relevant to the user query."""
    norm_query = normalize_text(query)
    query_tokens = set(tokenize(query))
    claims = load_claims_data()["claims"]

    scored: list[tuple[float, dict[str, Any]]] = []
    for claim in claims:
        score = 0.0
        for kw in claim.get("keywords", []):
            kw_norm = kw.lower()
            if " " in kw_norm:
                if kw_norm in norm_query:
                    score += 2.0
            elif re.search(rf"\b{re.escape(kw_norm)}\b", norm_query):
                score += 1.25
            elif kw_norm in query_tokens:
                score += 1.0

        claim_tokens = set(tokenize(claim["claim_text"]))
        overlap = query_tokens.intersection(claim_tokens)
        score += 0.6 * len(overlap)

        if score >= min_score:
            scored.append((score, claim))

    scored.sort(key=lambda item: (-item[0], item[1]["claim_id"]))
    return [item[1] for item in scored]


def detect_uncovered_topics(query: str) -> list[dict[str, Any]]:
    """Identify any explicitly uncovered topics referenced in the query."""
    norm_query = normalize_text(query)
    uncovered = load_claims_data().get("uncovered_topics", [])
    matches: list[dict[str, Any]] = []

    for entry in uncovered:
        for kw in entry.get("keywords", []):
            if re.search(rf"\b{re.escape(kw.lower())}\b", norm_query):
                matches.append(entry)
                break
    return matches
