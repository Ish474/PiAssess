"""AI question generation service.

Provider-independent: any OpenAI-compatible chat-completions endpoint
(OpenRouter, OpenAI, Zhipu, Ollama, LM Studio...) configured via Settings
or environment variables. Verification of answers is done here with SymPy —
an AI-generated answer is NEVER trusted on its own.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field

import httpx
import sympy
from sqlalchemy.orm import Session

from ..models import QUESTION_TYPES, DIFFICULTIES
from .common import get_setting

MAX_CONTENT_CHARS = 12000  # syllabus excerpt sent to the model


class AIConfigError(Exception):
    pass


class AIGenerationError(Exception):
    pass


@dataclass
class AIConfig:
    base_url: str
    api_key: str
    model: str

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model)


def get_ai_config(db: Session) -> AIConfig:
    """Environment variables take priority over stored settings (keys never in code)."""
    base = os.getenv("PIASSESS_AI_BASE_URL") or get_setting(db, "ai_base_url")
    key = os.getenv("PIASSESS_AI_API_KEY") or get_setting(db, "ai_api_key")
    model = os.getenv("PIASSESS_AI_MODEL") or get_setting(db, "ai_model")
    base = (base or "").strip().rstrip("/")
    return AIConfig(base_url=base, api_key=(key or "").strip(), model=(model or "").strip())


def chat_complete(db: Session, messages: list[dict], *, temperature: float = 0.7, timeout: float = 180.0) -> str:
    """One chat completion against the configured provider. Returns the message content.

    Transient failures (429 rate limit, 5xx high demand — common on free tiers)
    are retried automatically with a short backoff before giving up.
    """
    cfg = get_ai_config(db)
    if not cfg.configured:
        raise AIConfigError(
            "The AI provider is not configured yet. Open Settings -> AI Provider and fill in the address, model and API key."
        )
    url = f"{cfg.base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    body = {"model": cfg.model, "messages": messages, "temperature": temperature}

    backoffs = (2.0, 6.0)
    last_status, last_text = 0, ""
    for attempt in range(len(backoffs) + 1):
        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=timeout)
        except httpx.HTTPError as exc:
            raise AIGenerationError(
                f"Could not reach the AI provider ({cfg.base_url}). Check the internet connection and the address in Settings. ({exc.__class__.__name__})"
            ) from exc
        last_status, last_text = resp.status_code, resp.text[:200]
        if resp.status_code == 200:
            try:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError) as exc:
                raise AIGenerationError("The AI provider returned an unexpected response format.") from exc
        if resp.status_code in (401, 403):
            raise AIGenerationError("The AI provider rejected the API key. Check it in Settings -> AI Provider.")
        if resp.status_code == 429:
            body = resp.text
            m = re.search(r"retry in ([0-9hms\.]+)", body, re.IGNORECASE)
            wait_hint = f" It resets in about {m.group(1).rstrip('.')}." if m else ""
            if "per day" in body.lower():
                # Daily pool exhausted — retrying now is pointless and honest pacing beats wasted calls.
                raise AIGenerationError(
                    "The AI key's daily quota is used up." + wait_hint +
                    " You can wait for the reset, or enable pay-as-you-go billing on the key at aistudio.google.com/apikey for much higher limits."
                )
            # per-minute style limit: one patient retry, then clear guidance
            if attempt < len(backoffs):
                time.sleep(20.0)
                continue
            raise AIGenerationError(
                "The AI provider is rate-limiting requests. Wait a minute and press Generate again." + wait_hint
            )
        if resp.status_code in (500, 502, 503, 504) and attempt < len(backoffs):
            time.sleep(backoffs[attempt])
            continue
        break

    if last_status == 429:
        m = re.search(r"retry in ([0-9hms\.]+)", last_text, re.IGNORECASE)
        raise AIGenerationError(
            "The AI provider is rate-limiting requests. Wait a moment and press Generate again."
            + (f" It resets in about {m.group(1).rstrip('.')}." if m else "")
        )
    if last_status in (500, 502, 503, 504):
        raise AIGenerationError(
            "The AI provider is busy right now (high demand). Automatic retries were tried — please press Generate again in a minute."
        )
    raise AIGenerationError(f"The AI provider returned an error ({last_status}). {last_text}")


# ---------------------------------------------------------------- JSON parsing
def _json_candidates(text: str):
    """Yield candidate substrings: whole text, fenced blocks, then every balanced {...}
    (string-aware, so braces inside JSON strings don't break the scan)."""
    yield text
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        yield fence.group(1).strip()
    in_str = escape = False
    depth, start = 0, -1
    for i, ch in enumerate(text):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                yield text[start : i + 1]
                start = -1


def parse_llm_json(raw: str) -> dict:
    """Robustly extract a JSON object from an LLM answer (tolerates ``` fences and prose)."""
    for candidate in _json_candidates(raw.strip()):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    raise AIGenerationError("The AI reply was not valid JSON. Please press Generate again — this usually works on the second try.")


# ---------------------------------------------------------------- SymPy verification
def _clean_number(text: str) -> str:
    text = text.strip().replace(",", "").replace("₹", "").replace("%", "").replace("°", "")
    text = re.sub(r"^(Rs\.?|INR)\s*", "", text, flags=re.IGNORECASE)
    return text


def verify_numeric_answer(check_expression: str, answer: str) -> bool | None:
    """True = mathematically correct, False = mismatch, None = cannot verify.

    The check_expression is arithmetic the generator claims produces the answer,
    e.g. "(15*40 + 2*60) / 12". SymPy evaluates both sides independently.
    """
    try:
        expr = sympy.sympify(_clean_number(check_expression), rational=True)
        target = sympy.sympify(_clean_number(answer), rational=True)
        if not expr.is_number or not target.is_number:
            return None
        diff = sympy.simplify(expr - target)
        if diff == 0:
            return True
        if diff.is_number:
            return abs(float(diff)) < 1e-9
        return False
    except Exception:  # sympify raises sympy.SympifyError, TypeError, ValueError...
        return None


# ---------------------------------------------------------------- prompt building
DIFFICULTY_LABELS = {"easy": "Easy", "moderate": "Moderate", "challenging": "Challenging", "advanced": "Advanced", "mixed": "Mixed"}


@dataclass
class GenRequest:
    class_name: str
    subject: str
    chapters: str = ""
    content_text: str = ""
    types: list[dict] = field(default_factory=list)  # [{type, count, difficulty, marks}]
    extra_instructions: str = ""
    avoid_texts: list[str] = field(default_factory=list)


def build_generation_prompt(req: GenRequest) -> list[dict]:
    type_lines = []
    total = 0
    for t in req.types:
        label = QUESTION_TYPES.get(t["type"], t["type"])
        diff = DIFFICULTY_LABELS.get(t.get("difficulty", "mixed"), "Mixed")
        marks = t.get("marks", 1)
        type_lines.append(f"- {t['count']} × {label} (difficulty: {diff}, {marks} mark{'s' if marks != 1 else ''} each)")
        total += t["count"]

    content_block = req.content_text[:MAX_CONTENT_CHARS] if req.content_text else "(no textbook extract supplied — rely on the standard syllabus for this class and subject)"
    avoid_block = "\n".join(f"- {t[:120]}" for t in req.avoid_texts[:30])

    system = (
        "You are an expert Indian school examination setter and subject teacher. "
        "You write original exam questions in clear, age-appropriate English, strictly grounded in the supplied syllabus material. "
        "You always double-check every factual claim and every calculation before answering. "
        "For numerical problems you provide a check_expression: a plain arithmetic expression (numbers and + - * / ( ) only) "
        "whose evaluated value equals the correct answer, so the answer can be verified computationally. "
        "Respond with ONLY a JSON object — no commentary, no markdown fences."
    )
    user = f"""Create {total} original examination questions.

EXAM CONTEXT
- School class: {req.class_name}
- Subject: {req.subject}
- Chapters: {req.chapters or "(as per the supplied material)"}

LEARNING MATERIAL (source of truth)
{content_block}

REQUIRED QUESTIONS
{chr(10).join(type_lines)}

ALLOWED "type" KEYS — in the JSON, use EXACTLY one of these strings:
{", ".join(QUESTION_TYPES.keys())}

RULES
1. Questions must be original — do not copy sentences from the material.
2. No two questions may test the same fact in the same way.
3. Each question must be answerable at the specified difficulty for this class.
4. For mcq: give exactly 4 options (plain text). For true_false: options ["True", "False"] and correct_answer "True" or "False".
5. For numerical problems: correct_answer is ONLY the final number (no units in the answer field; mention units in the question), and you MUST include check_expression.
6. For fill_blank: use ______ for the blank; correct_answer is the word/phrase that fills it.
7. For match_following: put both columns inside the question text as "List-I ... List-II ..." lines; correct_answer gives the correct matches like "1-C, 2-A, 3-B".
8. For assertion_reason: question text contains "Assertion (A): ... Reason (R): ..." and options are the standard four (A/B/C/D both-true combinations).
9. For case_based: include the case/passage in the question text.
10. explanation must teach the method; keywords list 2-5 expected key terms; marking_notes describe step-wise mark allocation.
{f"11. Do not repeat or closely resemble these existing questions:{chr(10)}{avoid_block}" if avoid_block else ""}
{f"EXTRA INSTRUCTIONS FROM THE TEACHER: {req.extra_instructions}" if req.extra_instructions else ""}

Return JSON exactly in this shape:
{{
  "questions": [
    {{
      "type": "mcq",
      "difficulty": "easy",
      "marks": 1,
      "text": "...",
      "options": ["(A) ...", "(B) ...", "(C) ...", "(D) ..."],
      "correct_answer": "(B) ...",
      "explanation": "...",
      "keywords": ["...", "..."],
      "marking_notes": "...",
      "check_expression": ""
    }}
  ]
}}
"options" must be [] for non-MCQ types. "check_expression" must be "" except for numerical problems."""

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# LLMs often paraphrase type names ("application_based", "Fill in the Blanks").
# Map every reasonable variant to the canonical QUESTION_TYPES key.
TYPE_SYNONYMS: dict[str, str] = {
    "mcq": "mcq", "multiple_choice": "mcq", "multiple_choice_question": "mcq",
    "fill_blank": "fill_blank", "fill_in_the_blank": "fill_blank", "fill_in_the_blanks": "fill_blank",
    "fill_blanks": "fill_blank", "fill": "fill_blank", "fillups": "fill_blank", "fill_up": "fill_blank",
    "true_false": "true_false", "true_or_false": "true_false", "truefalse": "true_false", "tf": "true_false",
    "match_following": "match_following", "match_the_following": "match_following",
    "match_the_followings": "match_following", "matching": "match_following",
    "very_short": "very_short", "very_short_answer": "very_short", "vsa": "very_short",
    "short": "short", "short_answer": "short", "sa": "short",
    "long": "long", "long_answer": "long", "la": "long",
    "numerical": "numerical", "numerical_problem": "numerical", "numerical_problems": "numerical",
    "numeric": "numerical", "numericals": "numerical",
    "case_based": "case_based", "case_study": "case_based", "case": "case_based",
    "assertion_reason": "assertion_reason", "assertion_and_reason": "assertion_reason", "assertion": "assertion_reason",
    "logical_reasoning": "logical_reasoning", "logic_reasoning": "logical_reasoning",
    "reasoning": "logical_reasoning", "logic": "logical_reasoning",
    "application": "application", "application_based": "application",
    "application_based_question": "application", "application_questions": "application", "applied": "application",
    "hots": "hots", "hot": "hots", "higher_order_thinking": "hots", "higher_order_thinking_skills": "hots",
}


def canonical_qtype(raw: str) -> str | None:
    """Map an LLM-provided type name to the canonical key, or None if truly unknown."""
    key = re.sub(r"[\s\-]+", "_", raw.strip().lower()).strip("_")
    if key in TYPE_SYNONYMS:
        return TYPE_SYNONYMS[key]
    if key in QUESTION_TYPES:
        return key
    return None


def normalize_draft(raw_question: dict, allowed_types: dict[str, str]) -> dict:
    """Validate and normalise one draft question from the LLM."""
    raw_type = str(raw_question.get("type", "")).strip()
    qtype = canonical_qtype(raw_type)
    if qtype is None or qtype not in allowed_types:
        raise AIGenerationError(f"The AI returned an unknown question type \"{raw_type}\".")
    text = str(raw_question.get("text", "")).strip()
    if not text:
        raise AIGenerationError("The AI returned an empty question.")
    difficulty = str(raw_question.get("difficulty", "moderate")).strip().lower()
    if difficulty not in DIFFICULTIES:
        difficulty = "moderate"
    try:
        marks = max(1, int(raw_question.get("marks", 1)))
    except (TypeError, ValueError):
        marks = 1
    options = [str(o).strip() for o in (raw_question.get("options") or []) if str(o).strip()]
    answer = str(raw_question.get("correct_answer", "")).strip()
    keywords = [str(k).strip() for k in (raw_question.get("keywords") or []) if str(k).strip()]
    return {
        "qtype": qtype,
        "difficulty": difficulty,
        "marks": marks,
        "text": text,
        "options": options,
        "correct_answer": answer,
        "explanation": str(raw_question.get("explanation", "")).strip(),
        "keywords": keywords,
        "marking_notes": str(raw_question.get("marking_notes", "")).strip(),
        "check_expression": str(raw_question.get("check_expression", "")).strip(),
    }


def content_hash_of(qtype: str, text: str, correct_answer: str) -> str:
    normalized = " ".join(re.sub(r"\s+", " ", f"{qtype}|{text}|{correct_answer}".lower()).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
