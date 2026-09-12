"""Observed chat assessment helpers for imported Captain Cutlass history.

These helpers classify messages and aggregate user-level signals. They are
intentionally conservative: labels describe observed chat patterns, not moral
character, diagnoses, or fixed private traits.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

POSITIVE_PATTERNS = {
    "helpful": (
        "help", "helped", "helping", "helpful", "support", "supported",
        "thanks", "thank you", "appreciate", "good job", "nice work",
    ),
    "friendly": (
        "welcome", "glad", "good morning", "good night", "goodnight",
        "buddy", "friend", "love you", "miss you", "happy birthday",
    ),
    "humor": (
        "lol", "lmao", "haha", "funny", "joke", "meme", "rofl",
    ),
    "crew_first": (
        "crew", "team", "together", "donate", "donated", "contribute",
        "treasury", "ship", "repair", "work", "job", "helpful crewmate",
    ),
    "constructive": (
        "fix", "fixed", "build", "built", "improve", "upgrade", "idea",
        "plan", "test", "works", "working", "feature", "setup",
    ),
}

CONCERN_PATTERNS = {
    "conflict": (
        "argue", "argument", "drama", "beef", "fight", "fighting",
        "hostile", "toxic", "rage", "angry", "mad at", "annoyed",
    ),
    "insulting": (
        "idiot", "stupid", "dumb", "trash", "garbage", "moron", "clown",
        "shut up", "sucks", "hate you",
    ),
    "threatening": (
        "threat", "threaten", "kill you", "hurt you", "beat you",
        "destroy you", "dox", "doxx", "raid", "harass",
    ),
    "moderation": (
        "ban", "banned", "kick", "kicked", "mute", "muted", "warn", "warning",
        "report", "reported", "mod", "moderator-only",
    ),
    "disruptive": (
        "spam", "troll", "trolling", "grief", "griefing", "scam", "scammer",
        "exploit", "cheat", "cheating",
    ),
}

PROFANITY_RE = re.compile(r"\b(fuck|shit|damn|bitch|asshole)\b", re.I)
URL_RE = re.compile(r"https?://\S+", re.I)
MENTION_RE = re.compile(r"<@!?\d+>|<#[0-9]+>|<@&[0-9]+>")
SPACE_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    text = str(text or "")
    text = MENTION_RE.sub(" ", text)
    text = URL_RE.sub(" link ", text)
    text = SPACE_RE.sub(" ", text).strip()
    return text


def _count_terms(text: str, patterns: dict[str, tuple[str, ...]]):
    counts = Counter()
    lower = text.lower()
    for tag, terms in patterns.items():
        for term in terms:
            if " " in term:
                hits = lower.count(term)
            else:
                hits = len(re.findall(r"\b" + re.escape(term) + r"\b", lower))
            if hits:
                counts[tag] += hits
    return counts


def assess_message(content: str) -> dict:
    text = clean_text(content)
    positive = _count_terms(text, POSITIVE_PATTERNS)
    concern = _count_terms(text, CONCERN_PATTERNS)

    positive_score = sum(positive.values())
    negative_score = sum(concern.values())

    # Profanity is only a light concern by itself. In casual servers it often
    # means frustration or emphasis, so it should not dominate unless paired
    # with conflict/insult/threat language.
    profanity_hits = len(PROFANITY_RE.findall(text))
    if profanity_hits and negative_score:
        concern["heated_language"] += min(2, profanity_hits)
        negative_score += min(2, profanity_hits)

    tags = []
    tags.extend(tag for tag, count in positive.most_common() if count > 0)
    tags.extend(tag for tag, count in concern.most_common() if count > 0)

    if negative_score >= positive_score + 2 and negative_score >= 2:
        sentiment = "concern"
        assessment = "Concern signal in stored chat"
    elif positive_score >= negative_score + 2 and positive_score >= 2:
        sentiment = "positive"
        assessment = "Positive/useful signal in stored chat"
    elif positive_score or negative_score:
        sentiment = "mixed"
        assessment = "Mixed or context-dependent stored chat signal"
    else:
        sentiment = "neutral"
        assessment = "Neutral/limited stored chat signal"

    return {
        "sentiment": sentiment,
        "assessment": assessment,
        "positive_score": int(positive_score),
        "negative_score": int(negative_score),
        "tags": tags[:8],
        "excerpt": text[:220],
    }


def aggregate_assessments(rows: list[dict]) -> dict[tuple[int, int], dict]:
    grouped = defaultdict(lambda: {
        "total": 0,
        "positive": 0,
        "concern": 0,
        "mixed": 0,
        "neutral": 0,
        "positive_score": 0,
        "negative_score": 0,
        "tags": Counter(),
        "examples": [],
        "username": "",
    })

    for row in rows:
        key = (int(row["guild_id"]), int(row["user_id"]))
        bucket = grouped[key]
        sentiment = row.get("sentiment") or "neutral"
        bucket["total"] += 1
        bucket[sentiment] = int(bucket.get(sentiment, 0)) + 1
        bucket["positive_score"] += int(row.get("positive_score") or 0)
        bucket["negative_score"] += int(row.get("negative_score") or 0)
        bucket["username"] = row.get("username") or bucket["username"]
        raw_tags = row.get("tags") or []
        if isinstance(raw_tags, str):
            raw_tags = parse_tags(raw_tags)
        for tag in raw_tags:
            bucket["tags"][tag] += 1
        if sentiment in {"positive", "concern", "mixed"} and len(bucket["examples"]) < 4:
            bucket["examples"].append(row.get("excerpt") or "")

    return grouped


def user_assessment_label(bucket: dict) -> str:
    total = max(1, int(bucket.get("total") or 0))
    positive = int(bucket.get("positive") or 0)
    concern = int(bucket.get("concern") or 0)
    mixed = int(bucket.get("mixed") or 0)
    positive_score = int(bucket.get("positive_score") or 0)
    negative_score = int(bucket.get("negative_score") or 0)

    concern_ratio = concern / total
    positive_ratio = positive / total

    if total < 3 and positive_score == 0 and negative_score == 0:
        return "Limited / Neutral"
    if concern >= 3 and (concern_ratio >= 0.25 or negative_score >= positive_score + 5):
        return "Watch / Concern Signals"
    if concern >= 1 and positive >= 1:
        return "Mixed Signals"
    if positive >= 3 and positive_ratio >= 0.25 and negative_score <= positive_score:
        return "Mostly Positive"
    if positive_score >= negative_score + 3:
        return "Generally Positive"
    if negative_score > positive_score:
        return "Needs Context"
    if mixed:
        return "Mixed / Context Needed"
    return "Limited / Neutral"


def assessment_summary(bucket: dict) -> str:
    label = user_assessment_label(bucket)
    total = int(bucket.get("total") or 0)
    positive = int(bucket.get("positive") or 0)
    concern = int(bucket.get("concern") or 0)
    mixed = int(bucket.get("mixed") or 0)
    neutral = int(bucket.get("neutral") or 0)
    tags = [tag for tag, _ in bucket.get("tags", Counter()).most_common(5)]
    tag_text = ", ".join(tags) if tags else "no strong repeated tags"
    return (
        "Stored-message assessment: "
        + label
        + ". Signals from "
        + str(total)
        + " stored message(s): "
        + str(positive)
        + " positive, "
        + str(mixed)
        + " mixed, "
        + str(concern)
        + " concern, "
        + str(neutral)
        + " neutral. Common tags: "
        + tag_text
        + ". This describes observed chat patterns, not character."
    )


def tags_json(tags) -> str:
    return json.dumps(list(tags or [])[:8], ensure_ascii=False)


def parse_tags(value: str):
    try:
        parsed = json.loads(value or "[]")
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except Exception:
        pass
    return []
