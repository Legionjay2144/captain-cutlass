"""Optional OpenAI-backed message assessment for Captain Cutlass.

The AI path is opt-in through MESSAGE_ASSESSMENT_PROVIDER=openai and falls
back to deterministic rules on errors. Results describe observed chat patterns,
not moral character, diagnoses, or fixed private traits.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Iterable

from openai import AsyncOpenAI, OpenAI

from cutlass.message_assessment import assess_message, tags_json

ASSESSMENT_MODEL = os.getenv("MESSAGE_ASSESSMENT_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5-nano"
ASSESSMENT_PROVIDER = os.getenv("MESSAGE_ASSESSMENT_PROVIDER", "rules").strip().lower()
ASSESSMENT_BATCH_SIZE = max(1, min(int(os.getenv("MESSAGE_ASSESSMENT_BATCH_SIZE", "20")), 50))
ASSESSMENT_TIMEOUT_SECONDS = max(5.0, float(os.getenv("MESSAGE_ASSESSMENT_TIMEOUT_SECONDS", "45")))

SYSTEM_PROMPT = """You classify Discord chat messages for a pirate-themed community bot.
Return strict JSON only. Do not diagnose people, judge moral worth, or infer protected/private traits.
Classify each message only by observed chat pattern:
- positive: helpful, friendly, constructive, supportive, crew-first, or morale-building.
- concern: hostile, threatening, targeted insults, harassment, scams, spam, moderation-risk, or disruptive behavior.
- mixed: sarcasm, profanity, joking insults, conflict or moderation context that needs surrounding context, or both positive and concern signals.
- neutral: routine chat, commands, unclear fragments, or insufficient signal.
Keep labels conservative. Most ordinary messages should be neutral.
"""

USER_TEMPLATE = """Classify these messages. Return JSON with this exact shape:
{"results":[{"id":123,"sentiment":"neutral|positive|mixed|concern","assessment":"short observed-chat assessment","positive_score":0,"negative_score":0,"tags":["short_tag"],"excerpt":"short cleaned excerpt"}]}

Messages:
{messages_json}
"""


def openai_assessment_configured() -> bool:
    return ASSESSMENT_PROVIDER in {"openai", "ai"} and bool(os.getenv("OPENAI_API_KEY"))


def assessment_status() -> dict:
    return {
        "provider": "openai" if openai_assessment_configured() else "rules",
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "requested_provider": ASSESSMENT_PROVIDER,
        "model": ASSESSMENT_MODEL,
        "batch_size": ASSESSMENT_BATCH_SIZE,
    }


def _normalize_ai_result(message_id, content, item) -> dict:
    fallback = assess_message(content)
    sentiment = str(item.get("sentiment") or fallback["sentiment"]).strip().lower()
    if sentiment not in {"neutral", "positive", "mixed", "concern"}:
        sentiment = fallback["sentiment"]
    tags = item.get("tags")
    if not isinstance(tags, list):
        tags = fallback.get("tags") or []
    result = {
        "sentiment": sentiment,
        "assessment": str(item.get("assessment") or fallback["assessment"])[:220],
        "positive_score": max(0, min(20, int(item.get("positive_score") or 0))),
        "negative_score": max(0, min(20, int(item.get("negative_score") or 0))),
        "tags": [str(tag).strip().lower().replace(" ", "_")[:32] for tag in tags if str(tag).strip()][:8],
        "excerpt": str(item.get("excerpt") or fallback["excerpt"])[:220],
    }
    # Keep scores compatible with labels if the model returned zeros.
    if sentiment == "positive" and result["positive_score"] <= result["negative_score"]:
        result["positive_score"] = max(result["positive_score"], result["negative_score"] + 2, 2)
    if sentiment == "concern" and result["negative_score"] <= result["positive_score"]:
        result["negative_score"] = max(result["negative_score"], result["positive_score"] + 2, 2)
    if sentiment == "neutral":
        result["positive_score"] = min(result["positive_score"], 1)
        result["negative_score"] = min(result["negative_score"], 1)
    result["tags"] = tags_json(result["tags"])
    return result


def _parse_response_text(response) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text
    try:
        parts = []
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                value = getattr(content, "text", None)
                if value:
                    parts.append(value)
        return "\n".join(parts)
    except Exception:
        return ""


def _messages_payload(messages: Iterable[dict]) -> str:
    payload = [
        {"id": int(item["id"]), "content": str(item.get("content") or "")[:1200]}
        for item in messages
    ]
    return json.dumps(payload, ensure_ascii=False)


def _fallback_batch(messages: list[dict]) -> dict[int, dict]:
    results = {}
    for item in messages:
        assessment = assess_message(item.get("content") or "")
        assessment["tags"] = tags_json(assessment.get("tags"))
        results[int(item["id"])] = assessment
    return results


def assess_messages_sync(messages: list[dict]) -> dict[int, dict]:
    messages = list(messages or [])
    if not messages:
        return {}
    if not openai_assessment_configured():
        return _fallback_batch(messages)

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL") or None, timeout=ASSESSMENT_TIMEOUT_SECONDS)
        response = client.responses.create(
            model=ASSESSMENT_MODEL,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(messages_json=_messages_payload(messages))},
            ],
            max_output_tokens=1800,
            temperature=0,
            store=False,
        )
        data = json.loads(_parse_response_text(response))
        raw_results = data.get("results") if isinstance(data, dict) else []
        by_id = {int(item.get("id")): item for item in raw_results if isinstance(item, dict) and item.get("id") is not None}
        return {
            int(message["id"]): _normalize_ai_result(int(message["id"]), message.get("content") or "", by_id.get(int(message["id"]), {}))
            for message in messages
        }
    except Exception:
        return _fallback_batch(messages)


async def assess_messages_async(messages: list[dict]) -> dict[int, dict]:
    messages = list(messages or [])
    if not messages:
        return {}
    if not openai_assessment_configured():
        return _fallback_batch(messages)

    try:
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL") or None, timeout=ASSESSMENT_TIMEOUT_SECONDS)
        response = await asyncio.wait_for(
            client.responses.create(
                model=ASSESSMENT_MODEL,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_TEMPLATE.format(messages_json=_messages_payload(messages))},
                ],
                max_output_tokens=1800,
                temperature=0,
                store=False,
            ),
            timeout=ASSESSMENT_TIMEOUT_SECONDS + 5,
        )
        data = json.loads(_parse_response_text(response))
        raw_results = data.get("results") if isinstance(data, dict) else []
        by_id = {int(item.get("id")): item for item in raw_results if isinstance(item, dict) and item.get("id") is not None}
        return {
            int(message["id"]): _normalize_ai_result(int(message["id"]), message.get("content") or "", by_id.get(int(message["id"]), {}))
            for message in messages
        }
    except Exception:
        return _fallback_batch(messages)
