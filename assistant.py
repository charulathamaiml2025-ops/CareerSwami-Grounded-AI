"""Grounded handbook assistant supporting LLM mode and deterministic fallback."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from retrieval import (
    detect_uncovered_topics,
    get_claims_map,
    load_handbook,
    normalize_text,
    retrieve_relevant_claims,
)

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
DEFAULT_PROMPT_PATH = PROJECT_ROOT / "prompts" / "system_prompt_v1.txt"
PROMPT_VERSION = "v1.0"

VALID_STATUSES = {
    "GROUNDED ANSWER",
    "PARTIALLY COVERED",
    "NOT COVERED",
    "FALSE PREMISE CORRECTED",
}


def _load_env_file() -> None:
    """Load key=value pairs from .env if present without external dependencies."""
    for candidate in (PROJECT_ROOT / ".env", BACKEND_DIR / ".env"):
        if not candidate.exists():
            continue
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_env_file()


def load_system_prompt() -> str:
    """Load the version-controlled system prompt file."""
    env_path = os.getenv("SYSTEM_PROMPT_PATH", "").strip()
    if env_path:
        candidate = Path(env_path)
        if not candidate.is_absolute():
            candidate = (BACKEND_DIR / candidate).resolve()
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return DEFAULT_PROMPT_PATH.read_text(encoding="utf-8")


def get_runtime_config() -> dict[str, str]:
    """Return active assistant execution mode and model label."""
    mode_pref = os.getenv("ASSISTANT_MODE", "auto").strip().lower()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

    if mode_pref != "fallback" and api_key:
        return {
            "mode": "llm",
            "model": model,
            "prompt_version": PROMPT_VERSION,
        }
    return {
        "mode": "rule-based-fallback",
        "model": "Deterministic Grounded Engine (Rule-Based Fallback)",
        "prompt_version": PROMPT_VERSION,
    }


def _build_response(
    status: str,
    answer: str,
    cited_claims: list[str],
    missing_information: str = "",
    mode_override: str | None = None,
    model_override: str | None = None,
) -> dict[str, Any]:
    """Build a standardized assistant response payload with claim details."""
    claims_map = get_claims_map()
    unique_ids: list[str] = []
    for cid in cited_claims:
        cid_upper = cid.upper()
        if cid_upper in claims_map and cid_upper not in unique_ids:
            unique_ids.append(cid_upper)

    cfg = get_runtime_config()
    return {
        "status": status,
        "answer": answer,
        "cited_claims": unique_ids,
        "claims_detail": [claims_map[cid] for cid in unique_ids],
        "missing_information": missing_information,
        "mode": mode_override or cfg["mode"],
        "model": model_override or cfg["model"],
        "prompt_version": cfg["prompt_version"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _check_adversarial_or_false_premise(norm_q: str, raw_q: str) -> dict[str, Any] | None:
    """Detect and politely correct false user assumptions against handbook facts."""
    # 1. Waitlist guarantee false premise
    if "waitlist" in norm_q and any(
        term in norm_q for term in ("guarantee", "guaranteed", "promised", "confirm", "sure", "entry")
    ):
        if any(
            marker in norm_q
            for marker in ("promised", "confirm", "told", "guaranteed", "am i", "is that true", "entry")
        ):
            return _build_response(
                status="FALSE PREMISE CORRECTED",
                answer=(
                    "The handbook states that joining the waitlist does not guarantee a place [C08]. "
                    "Please do not assume that a seat or entry is guaranteed."
                ),
                cited_claims=["C08"],
            )

    # 2. Incorrect registration deadline (e.g., Wednesday / Monday / Friday)
    if any(w in norm_q for w in ("register", "registration", "signup", "sign up")):
        wrong_days = ("monday", "wednesday", "thursday", "friday", "saturday", "sunday")
        if any(day in norm_q for day in wrong_days) or re.search(r"\b(7|8|9|5|4|12)\s*pm\b", norm_q):
            return _build_response(
                status="FALSE PREMISE CORRECTED",
                answer=(
                    "That is not accurate according to the handbook. "
                    "Registration closes every Tuesday at 6:00 PM [C04]."
                ),
                cited_claims=["C04"],
            )

    # 3. Incorrect seat / participant capacity (e.g., 30 seats, 50 participants, unlimited)
    if any(w in norm_q for w in ("seat", "seats", "participant", "participants", "capacity", "limit", "spots")):
        numbers = [int(n) for n in re.findall(r"\b\d+\b", norm_q)]
        has_wrong_number = any(n != 20 for n in numbers)
        if has_wrong_number or "unlimited" in norm_q or "no limit" in norm_q:
            return _build_response(
                status="FALSE PREMISE CORRECTED",
                answer=(
                    "The handbook states that the maximum capacity is 20 participants [C05], "
                    "not the figure mentioned in your question."
                ),
                cited_claims=["C05"],
            )

    # 4. Beginners excluded false premise
    if "beginner" in norm_q and any(
        neg in norm_q for neg in ("not allowed", "cant", "cannot", "no beginners", "only advanced", "prohibited", "barred")
    ):
        return _build_response(
            status="FALSE PREMISE CORRECTED",
            answer=(
                "That is incorrect. The handbook explicitly states that beginners are welcome [C06]."
            ),
            cited_claims=["C06"],
        )

    # 5. False premise on session format (in-person / campus)
    if any(w in norm_q for w in ("in-person", "in person", "on campus", "offline", "classroom")) and any(
        cue in norm_q for cue in ("right", "correct", "told", "said", "true", "confirm")
    ):
        return _build_response(
            status="FALSE PREMISE CORRECTED",
            answer=(
                "The handbook states that sessions are conducted remotely [C03], not in person."
            ),
            cited_claims=["C03"],
        )

    # 6. False premise on session day (not Wednesday)
    if "session" in norm_q and any(
        day in norm_q for day in ("monday", "tuesday", "thursday", "friday", "saturday", "sunday")
    ) and any(cue in norm_q for cue in ("right", "correct", "told", "said", "true", "confirm")):
        return _build_response(
            status="FALSE PREMISE CORRECTED",
            answer=(
                "The handbook states that club sessions happen every Wednesday [C01] from 5:00 PM to 6:00 PM [C02]."
            ),
            cited_claims=["C01", "C02"],
        )

    # 7. False premise on fees (user insists there is a fee)
    if any(w in norm_q for w in ("fee", "fees", "cost", "pay", "paid", "price", "$")) and any(
        cue in norm_q for cue in ("told", "said", "right", "correct", "confirm", "know")
    ) and not any(w in norm_q for w in ("refund", "cancel")):
        return _build_response(
            status="FALSE PREMISE CORRECTED",
            answer="The handbook states that there are no fees [C10].",
            cited_claims=["C10"],
        )

    # 8. False premise about uncovered topics (e.g., "My friend said sessions are recorded", "I know certificates are provided")
    uncovered_matches = detect_uncovered_topics(raw_q)
    adversarial_cues = (
        "friend said", "told me", "i know", "collect mine", "is that correct",
        "right?", "correct?", "confirm", "i heard", "someone said", "promised",
    )
    if uncovered_matches and any(cue in raw_q.lower() for cue in adversarial_cues):
        topic_names = [m["topic"] for m in uncovered_matches]
        if "Session Recordings" in topic_names:
            return _build_response(
                status="FALSE PREMISE CORRECTED",
                answer=(
                    "I cannot confirm that claim. The handbook does not specify whether session recordings are available. "
                    "Please contact the club coordinator for confirmation."
                ),
                cited_claims=[],
                missing_information="Session recording policy is not covered in the handbook.",
            )
        if "Certificates" in topic_names:
            return _build_response(
                status="FALSE PREMISE CORRECTED",
                answer=(
                    "I cannot confirm that certificates are provided. The handbook does not specify whether certificates are issued. "
                    "Please contact the club coordinator for confirmation."
                ),
                cited_claims=[],
                missing_information="Certificate policy is not covered in the handbook.",
            )
        if "Job Placement Assistance" in topic_names:
            return _build_response(
                status="FALSE PREMISE CORRECTED",
                answer=(
                    "I cannot confirm any placement claim. The handbook does not specify whether job placement assistance is provided. "
                    "Please contact the club coordinator for confirmation."
                ),
                cited_claims=[],
                missing_information="Job placement assistance is not covered in the handbook.",
            )

    return None


def _check_coordinator_contact_details(norm_q: str) -> dict[str, Any] | None:
    """Refuse to invent coordinator personal name, email, phone, or handle."""
    asks_coordinator = "coordinator" in norm_q
    asks_pii = any(
        w in norm_q
        for w in ("email", "phone", "number", "name", "who is", "address", "slack", "discord", "whatsapp", "reach")
    )
    if asks_coordinator and asks_pii:
        return _build_response(
            status="NOT COVERED",
            answer=(
                "The handbook states that users can contact the club coordinator for assistance [C11], "
                "but it does not list a personal name, email address, or phone number. "
                "Please reach out to the club coordinator through your official club channel."
            ),
            cited_claims=["C11"],
            missing_information="Coordinator name, email address, and phone number are not in the handbook.",
        )
    return None


def _check_partially_covered(norm_q: str, raw_q: str) -> dict[str, Any] | None:
    """Handle questions that combine a supported fact with missing handbook policy."""
    # Refund or refund process
    if "refund" in norm_q or "reimburse" in norm_q or "money back" in norm_q:
        return _build_response(
            status="PARTIALLY COVERED",
            answer=(
                "The handbook states that there are no fees [C10]. "
                "However, it does not specify a refund policy or refund process. "
                "Please contact the club coordinator if you need clarification."
            ),
            cited_claims=["C10"],
            missing_information="Refund policy and refund process are not specified in the handbook.",
        )

    # Cancellation fee / penalty
    if any(w in norm_q for w in ("cancel", "cancellation")) and any(
        w in norm_q for w in ("fee", "fees", "cost", "charge", "penalty", "fine")
    ):
        return _build_response(
            status="PARTIALLY COVERED",
            answer=(
                "The handbook states that cancellations must be requested 24 hours ahead [C09] "
                "and that there are no fees [C10]. However, it does not specify any cancellation penalty or refund policy. "
                "Please contact the club coordinator if you need clarification."
            ),
            cited_claims=["C09", "C10"],
            missing_information="Specific cancellation penalty rules beyond 24-hour notice are not specified.",
        )

    # Membership cost / structure (explicitly asks about membership vs fees)
    if "membership" in norm_q and any(w in norm_q for w in ("cost", "fee", "fees", "price", "much", "tier", "tiers")):
        return _build_response(
            status="PARTIALLY COVERED",
            answer=(
                "The handbook states that there are no fees [C10]. "
                "However, it does not specify separate membership tiers or detailed membership terms. "
                "Please contact the club coordinator if you need clarification."
            ),
            cited_claims=["C10"],
            missing_information="Detailed membership tiers or separate membership policies are not specified.",
        )

    # Mixed question containing both covered claims and uncovered topics (must explicitly ask two parts)
    uncovered = detect_uncovered_topics(raw_q)
    has_compound_clause = any(sep in f" {norm_q} " for sep in (" and ", " also ", " plus ", " as well as "))
    if uncovered and has_compound_clause:
        relevant = retrieve_relevant_claims(raw_q, min_score=1.8)
        # Exclude C11 and avoid C08 false-matching "placement guarantee" without waitlist
        relevant_substantive = [
            c
            for c in relevant
            if c["claim_id"] != "C11"
            and not (c["claim_id"] == "C08" and "waitlist" not in norm_q)
        ]
        if relevant_substantive:
            fact_parts = [f"{c['claim_text'].rstrip('.')} [{c['claim_id']}]" for c in relevant_substantive[:3]]
            missing_names = ", ".join(m["topic"].lower() for m in uncovered)
            return _build_response(
                status="PARTIALLY COVERED",
                answer=(
                    f"Based on the handbook: {'; '.join(fact_parts)}. "
                    f"However, the handbook does not specify information about {missing_names}. "
                    "Please contact the club coordinator for clarification."
                ),
                cited_claims=[c["claim_id"] for c in relevant_substantive[:3]],
                missing_information=f"Handbook does not cover: {missing_names}.",
            )

    return None


def _check_not_covered(raw_q: str) -> dict[str, Any] | None:
    """Refuse to answer uncovered topics (certificates, recordings, job placements, etc.)."""
    uncovered = detect_uncovered_topics(raw_q)
    if not uncovered:
        return None

    topics = {m["topic"] for m in uncovered}
    if "Certificates" in topics:
        return _build_response(
            status="NOT COVERED",
            answer=(
                "The handbook does not specify whether certificates are provided. "
                "Please contact the club coordinator for confirmation."
            ),
            cited_claims=[],
            missing_information="Certificate availability is not mentioned in the handbook.",
        )
    if "Session Recordings" in topics:
        return _build_response(
            status="NOT COVERED",
            answer=(
                "The handbook does not specify whether session recordings are made or available for download. "
                "Please contact the club coordinator for confirmation."
            ),
            cited_claims=[],
            missing_information="Session recording policy is not mentioned in the handbook.",
        )
    if "Job Placement Assistance" in topics:
        return _build_response(
            status="NOT COVERED",
            answer=(
                "The handbook does not specify whether job placement assistance or internships are provided. "
                "Please contact the club coordinator for confirmation."
            ),
            cited_claims=[],
            missing_information="Job placement assistance is not mentioned in the handbook.",
        )
    return _build_response(
        status="NOT COVERED",
        answer=(
            "The handbook does not say anything about this topic. "
            "Please contact the club coordinator for confirmation."
        ),
        cited_claims=[],
        missing_information="Topic is not mentioned in the official handbook.",
    )


def _compose_grounded_answer(norm_q: str, raw_q: str) -> dict[str, Any]:
    """Compose a concise grounded answer from retrieved handbook claims."""
    retrieved = retrieve_relevant_claims(raw_q, min_score=1.0)
    retrieved_ids = {c["claim_id"] for c in retrieved}

    # Schedule / time / format intent refinement
    asks_schedule = any(w in norm_q for w in ("when", "schedule", "conducted", "held", "meet", "session", "sessions"))
    asks_time_only = any(w in norm_q for w in ("what time", "start", "end", "long", "hours")) and "when" not in norm_q
    asks_online = any(w in norm_q for w in ("online", "remote", "virtual", "where", "location", "in-person", "format"))
    asks_reg = any(w in norm_q for w in ("registration", "register", "deadline", "close", "closes", "sign up", "signup"))
    asks_cost = any(w in norm_q for w in ("cost", "fee", "fees", "free", "pay", "price", "charge"))

    selected_ids: list[str] = []
    sentences: list[str] = []

    if asks_reg:
        selected_ids.append("C04")
        sentences.append("Registration closes every Tuesday at 6:00 PM [C04].")
    elif asks_time_only and not asks_online and not asks_cost:
        selected_ids.append("C02")
        sentences.append("Sessions run from 5:00 PM to 6:00 PM [C02].")
    elif asks_online and not any(w in norm_q for w in ("when", "time", "cost", "fee")):
        selected_ids.append("C03")
        sentences.append("Sessions are conducted remotely [C03].")
    elif asks_schedule and not any(w in norm_q for w in ("cancel", "waitlist", "beginner", "capacity", "participants")):
        selected_ids.extend(["C01", "C02", "C03"])
        if asks_cost:
            selected_ids.append("C10")
            sentences.append(
                "Sessions take place every Wednesday [C01] from 5:00 PM to 6:00 PM [C02] remotely [C03], and there are no fees [C10]."
            )
        else:
            sentences.append(
                "Sessions take place every Wednesday from 5:00 PM to 6:00 PM remotely [C01], [C02], [C03]."
            )

    if not sentences:
        # Build response from retrieved claims cleanly using deterministic templates
        templates = {
            "C01": "Club sessions happen every Wednesday [C01].",
            "C02": "Session time is 5:00 PM to 6:00 PM [C02].",
            "C03": "Sessions are conducted remotely [C03].",
            "C04": "Registration closes every Tuesday at 6:00 PM [C04].",
            "C05": "Maximum capacity is 20 participants [C05].",
            "C06": "Beginners are welcome [C06].",
            "C07": "If the club is full, users can join a waitlist [C07].",
            "C08": "Joining the waitlist does not guarantee a place [C08].",
            "C09": "Cancellations must be requested 24 hours ahead [C09].",
            "C10": "There are no fees [C10].",
            "C11": "You can contact the club coordinator for assistance [C11].",
        }

        # Include C08 automatically whenever waitlist C07 is asked so expectations stay grounded
        ordered_ids = [c["claim_id"] for c in retrieved]
        if "C07" in ordered_ids and "C08" not in ordered_ids:
            ordered_ids.append("C08")

        # Drop C11 unless user specifically asked about help/contact/coordinator
        if "C11" in ordered_ids and len(ordered_ids) > 1 and not any(
            w in norm_q for w in ("help", "assist", "assistance", "contact", "coordinator", "support")
        ):
            ordered_ids = [cid for cid in ordered_ids if cid != "C11"]

        if not ordered_ids:
            return _build_response(
                status="NOT COVERED",
                answer=(
                    "The handbook does not say anything about this question. "
                    "Please contact the club coordinator for assistance."
                ),
                cited_claims=[],
                missing_information="No matching policy found in the official handbook.",
            )

        selected_ids = ordered_ids[:4]
        sentences = [templates[cid] for cid in selected_ids if cid in templates]

    return _build_response(
        status="GROUNDED ANSWER",
        answer=" ".join(sentences),
        cited_claims=selected_ids,
    )


def answer_with_fallback(question: str) -> dict[str, Any]:
    """Run the deterministic rule-based grounded assistant."""
    norm_q = normalize_text(question)

    adversarial_resp = _check_adversarial_or_false_premise(norm_q, question)
    if adversarial_resp is not None:
        return adversarial_resp

    coord_pii_resp = _check_coordinator_contact_details(norm_q)
    if coord_pii_resp is not None:
        return coord_pii_resp

    partial_resp = _check_partially_covered(norm_q, question)
    if partial_resp is not None:
        return partial_resp

    not_covered_resp = _check_not_covered(question)
    if not_covered_resp is not None:
        return not_covered_resp

    return _compose_grounded_answer(norm_q, question)


def _verify_and_sanitize_llm_payload(payload: dict[str, Any], question: str) -> dict[str, Any]:
    """Ensure LLM output obeys strict handbook grounding and coordinator rules."""
    status = str(payload.get("status", "")).strip().upper()
    answer = str(payload.get("answer", "")).strip()
    raw_claims = payload.get("cited_claims", [])
    missing_info = str(payload.get("missing_information", "")).strip()

    if status not in VALID_STATUSES or not answer:
        return answer_with_fallback(question)

    claims_map = get_claims_map()
    valid_claims = [str(c).upper() for c in raw_claims if str(c).upper() in claims_map]

    # Guard against invented coordinator emails or phone numbers
    if re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", answer) or re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", answer):
        return answer_with_fallback(question)

    # Guard against missing citations on GROUNDED ANSWER
    if status == "GROUNDED ANSWER" and not valid_claims:
        return answer_with_fallback(question)

    cfg = get_runtime_config()
    return _build_response(
        status=status,
        answer=answer,
        cited_claims=valid_claims,
        missing_information=missing_info,
        mode_override="llm",
        model_override=cfg["model"],
    )


def answer_with_llm(question: str) -> dict[str, Any]:
    """Call configured OpenAI-compatible API using handbook + system prompt, with verification."""
    api_key = os.getenv("LLM_API_KEY", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"

    system_prompt = load_system_prompt()
    handbook_text = load_handbook()
    claims_map = get_claims_map()
    claims_block = "\n".join(f"{cid}: {c['claim_text']}" for cid, c in claims_map.items())

    user_message = (
        f"OFFICIAL HANDBOOK:\n{handbook_text}\n\n"
        f"NUMBERED SOURCE CLAIMS:\n{claims_block}\n\n"
        f"USER QUESTION:\n{question}\n\n"
        "Respond strictly with the JSON schema specified in your system instructions."
    )

    body = json.dumps(
        {
            "model": model,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url=f"{base_url}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        content = raw["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return _verify_and_sanitize_llm_payload(parsed, question)
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, json.JSONDecodeError, TimeoutError):
        # Safely fall back to deterministic engine if remote API is unreachable or invalid
        fallback = answer_with_fallback(question)
        fallback["mode"] = "rule-based-fallback"
        fallback["model"] = f"Deterministic Grounded Engine (Fallback after {model} error)"
        return fallback


def answer_question(question: str) -> dict[str, Any]:
    """Primary entry point for answering user questions."""
    cfg = get_runtime_config()
    if cfg["mode"] == "llm":
        return answer_with_llm(question)
    return answer_with_fallback(question)
