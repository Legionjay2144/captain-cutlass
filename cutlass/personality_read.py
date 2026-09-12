PERSONALITY_ARCHETYPES = {
    "Shipwright Strategist": {
        "keywords": ("build", "built", "creator", "shipwright", "feature", "upgrade", "system", "server", "automation", "practical", "fix", "work", "maintain", "improve"),
        "traits": ("builder", "planner", "systems-minded", "improvement-driven"),
    },
    "Jester of the Crew": {
        "keywords": ("joke", "jokes", "pun", "puns", "funny", "laugh", "humor", "banter", "comedy", "quip", "tease"),
        "traits": ("playful", "humorous", "banter-friendly", "morale-lifting"),
    },
    "Treasure-Seeker": {
        "keywords": ("treasure", "loot", "doubloon", "gold", "reward", "hunt", "adventure", "explore", "discovery", "map"),
        "traits": ("adventurous", "reward-focused", "curious", "exploration-minded"),
    },
    "Loyal Deckhand": {
        "keywords": ("loyal", "trusted", "friend", "crew", "crewmate", "help", "helpful", "support", "donated", "contribution", "ship", "together"),
        "traits": ("loyal", "supportive", "crew-first", "dependable"),
    },
    "Chaos Spark": {
        "keywords": ("chaos", "mutiny", "trouble", "wild", "storm", "mischief", "dramatic", "bold", "lively"),
        "traits": ("energetic", "unpredictable", "bold", "high-spirited"),
    },
    "Quiet Newcomer": {
        "keywords": ("new", "joined", "welcome", "welcomed", "learning", "fresh", "new crewmate"),
        "traits": ("new", "developing", "lightly-known", "needs-more-context"),
    },
    "Lorekeeper": {
        "keywords": ("story", "stories", "tale", "lore", "memory", "remember", "old", "history", "canon", "legend"),
        "traits": ("story-driven", "memory-rich", "nostalgic", "lore-curious"),
    },
}

POSITIVE_TERMS = (
    "help", "helpful", "support", "trusted", "loyal", "friend", "welcome",
    "joke", "laugh", "fun", "donated", "contribution", "achievement",
    "treasure", "work", "repair", "crew", "kind", "cheer", "spirit",
)

CONCERN_TERMS = (
    "drama", "argument", "argue", "hostile", "insult", "mutiny", "threat",
    "kicked", "crushed", "accus", "trouble", "toxic", "rage", "angry",
)


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def infer_personality_type(signal_text, base=None):
    text = str(signal_text or "").lower()
    base = base or {}
    scores = {}
    evidence = {}

    for name, config in PERSONALITY_ARCHETYPES.items():
        score = 0
        hits = []
        for keyword in config["keywords"]:
            count = text.count(keyword)
            if count:
                score += count
                hits.append(keyword)
        scores[name] = score
        evidence[name] = hits[:6]

    familiarity = safe_int(base.get("familiarity"), 0)
    memory_count = safe_int(base.get("memory_count"), 0)
    joke_count = safe_int(base.get("joke_count"), 0)
    work_runs = safe_int(base.get("work_runs"), 0)
    ship_contributed = safe_int(base.get("ship_contributed"), 0)
    achievement_count = safe_int(base.get("achievement_count"), 0)
    message_count = safe_int(base.get("message_count"), 0)

    if familiarity >= 75:
        scores["Loyal Deckhand"] += 2
    if memory_count >= 5:
        scores["Lorekeeper"] += 1
    if joke_count >= 3:
        scores["Jester of the Crew"] += 2
    if work_runs >= 2 or ship_contributed > 0:
        scores["Loyal Deckhand"] += 2
    if achievement_count >= 5:
        scores["Treasure-Seeker"] += 1
    if message_count >= 50:
        scores["Loyal Deckhand"] += 1
    if message_count >= 150:
        scores["Lorekeeper"] += 1

    best_name, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score <= 0:
        best_name = "Quiet Newcomer"
        best_score = 1

    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    secondary = [name for name, score in sorted_scores[1:4] if score > 0]
    confidence = min(95, 25 + (best_score * 7) + min(20, memory_count + joke_count + achievement_count + (message_count // 25)))
    traits = list(PERSONALITY_ARCHETYPES[best_name]["traits"])
    if secondary:
        traits.extend(PERSONALITY_ARCHETYPES[secondary[0]]["traits"][:2])

    deduped_traits = []
    for trait in traits:
        if trait not in deduped_traits:
            deduped_traits.append(trait)

    return {
        "label": best_name,
        "confidence": confidence,
        "traits": deduped_traits[:6],
        "secondary": secondary,
        "evidence": evidence.get(best_name, []),
        "signal_count": len([line for line in str(signal_text or "").splitlines() if line.strip()]),
    }


def crew_read_label(signal_text, base=None):
    text = str(signal_text or "").lower()
    base = base or {}
    positive = sum(text.count(term) for term in POSITIVE_TERMS)
    concern = sum(text.count(term) for term in CONCERN_TERMS)
    familiarity = safe_int(base.get("familiarity"), 0)
    work_runs = safe_int(base.get("work_runs"), 0)
    ship_contributed = safe_int(base.get("ship_contributed"), 0)
    achievement_count = safe_int(base.get("achievement_count"), 0)
    message_count = safe_int(base.get("message_count"), 0)

    positive += min(4, familiarity // 25)
    positive += min(3, work_runs)
    positive += 2 if ship_contributed > 0 else 0
    positive += min(3, achievement_count // 2)
    positive += min(2, message_count // 100)

    if concern >= positive + 3 and concern >= 3:
        return "Potential Drama Risk"
    if concern >= 2 and positive >= 2:
        return "Mixed Signals"
    if positive >= 8 and concern == 0:
        return "Strong Crew Fit"
    if positive >= 4:
        return "Friendly / Positive"
    if concern >= 1:
        return "Needs Context"
    return "Not Enough Data"


def summarize_evidence(items, limit=3):
    result = []
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        if len(text) > 140:
            text = text[:139] + "…"
        result.append(text)
        if len(result) >= limit:
            break
    return result
