import random
import time


# Short-lived streak state.
# Key: (guild_id, user_id)
_tickle_streaks = {}

STREAK_RESET_SECONDS = 90
TICKLE_COOLDOWN_SECONDS = 2.0

# Secret persistent milestones.
MILESTONES = {
    10: "Ten times?! Ye've made this a hobby, haven't ye?",
    25: "Twenty-five tickles. I'm beginning to suspect piracy was the safer career.",
    50: "FIFTY?! Me ribs have filed a formal complaint with the Admiralty!",
    100: "ONE HUNDRED TICKLES?! UNHAND ME, YE PROFESSIONAL MENACE!",
    250: "Two hundred and fifty. At this point I'm adding tickle armor to the ship upgrades.",
    500: "FIVE HUNDRED?! Barnacle! Fetch me the anti-tickle cannon!",
    1000: "A THOUSAND TICKLES?! This is no longer mischief. This is a naval campaign!",
}


def _streak_key(guild_id, user_id):
    return (int(guild_id), int(user_id))


def register_tickle_streak(guild_id, user_id):
    """
    Record a short-term tickle and return:
        (accepted, streak)

    Very rapid duplicate attempts are rejected so Discord retries or
    accidental double submissions do not inflate the interaction.
    """
    key = _streak_key(guild_id, user_id)
    now = time.monotonic()

    state = _tickle_streaks.get(key)

    if state:
        elapsed = now - state["last"]

        if elapsed < TICKLE_COOLDOWN_SECONDS:
            return False, state["streak"]

        if elapsed <= STREAK_RESET_SECONDS:
            streak = state["streak"] + 1
        else:
            streak = 1
    else:
        streak = 1

    _tickle_streaks[key] = {
        "last": now,
        "streak": streak,
    }

    return True, streak


def _normal_reaction(streak):
    if streak <= 1:
        pool = [
            "Oi! What was that for?!",
            "Heh—watch the ribs, matey!",
            "GYAH! Ye sneaky little deck rat!",
            "Oi! These old bones weren't built for surprise tickles!",
            "Hah! Keep yer fingers to yerself, ye menace.",
        ]

    elif streak == 2:
        pool = [
            "Again?! I'm warning ye, these hands know retaliation!",
            "Twice?! Ye're testin' dangerous waters now.",
            "Oi! I felt that one in me wooden leg, and I don't even have one!",
            "Ye've had yer laugh. Don't make an old pirate get up.",
        ]

    elif streak == 3:
        pool = [
            "THREE TIMES?! This is becoming an organized attack!",
            "Barnacle! Witness this harassment!",
            "Right, that's three. I'm loading the tickle cannons.",
            "Ye've crossed from mischief into piracy, and I'M the pirate!",
        ]

    elif streak <= 5:
        pool = [
            "UNHAND ME, YE MENACE!",
            "STOP THAT! Me dignity's already hanging by a thread!",
            "I SWEAR ON ME LAST GOOD KNEE—",
            "This means war! A very silly, poorly organized war!",
            "Ye're going in the Captain's Log under 'persistent nuisances.'",
        ]

    else:
        pool = [
            "SOMEBODY RESTRAIN THIS CREWMATE!",
            "BARNACLE! DEFENSIVE FORMATION!",
            "ME RIBS! ME POOR ANCIENT RIBS!",
            "THIS SHIP HAS RULES! Probably! Somewhere!",
            "I'LL KEELHAUL YE WITH A FEATHER DUSTER!",
            "UNHAND ME, YE MENACE!",
        ]

    return random.choice(pool)


def _familiar_reaction(streak):
    if streak < 3:
        pool = [
            "Heh. Ye know me too well, don't ye?",
            "I should've known it'd be one of me regular troublemakers.",
            "Oi! Familiarity does NOT grant ye tickling privileges!",
        ]
    else:
        pool = [
            "I trusted ye! This is what familiarity gets me?!",
            "After all we've been through, ye choose tickle warfare?!",
            "Ye've been aboard long enough to know I'm ticklish, traitor!",
        ]

    return random.choice(pool)


def _creator_reaction(streak):
    if streak == 1:
        pool = [
            "Oi! Ye built me and THIS is what ye use that power for?!",
            "Shipwright! Keep yer hands off the merchandise!",
            "I knew giving me a creator would eventually become a design flaw.",
        ]
    elif streak <= 3:
        pool = [
            "Again?! Ye programmed these ribs too sensitive!",
            "I demand a firmware update with tickle resistance!",
            "Ye built me personality just so ye could torment it, didn't ye?",
        ]
    else:
        pool = [
            "CREATOR OR NOT, YE'RE GOING OVERBOARD!",
            "I'M PATCHING *YOU* OUT NEXT UPDATE!",
            "UNHAND ME, YE MENACE! I KNOW WHERE YE KEEP THE SOURCE CODE!",
            "That's it! I'm changing me own administrator permissions!",
        ]

    return random.choice(pool)


def build_tickle_reaction(
    *,
    streak,
    lifetime_count,
    familiarity=0,
    creator=False,
):
    """
    Produce Captain's reaction.

    Returns:
        {
            "text": str,
            "tickle_back": bool,
            "milestone": bool,
        }
    """

    # Exact secret milestones override ordinary reactions.
    milestone_text = MILESTONES.get(int(lifetime_count))

    if milestone_text:
        return {
            "text": milestone_text,
            "tickle_back": False,
            "milestone": True,
        }

    # Very rare universal dramatic response.
    if random.random() < 0.025:
        return {
            "text": "UNHAND ME, YE MENACE!",
            "tickle_back": False,
            "milestone": False,
        }

    if creator:
        text = _creator_reaction(streak)

    elif int(familiarity or 0) >= 50 and random.random() < 0.40:
        text = _familiar_reaction(streak)

    else:
        text = _normal_reaction(streak)

    # Retaliation becomes more likely during repeated attacks.
    tickle_back_chance = min(
        0.08 + max(0, streak - 1) * 0.06,
        0.35,
    )

    tickle_back = random.random() < tickle_back_chance

    if tickle_back:
        retaliation = random.choice([
            " Captain lunges back with a retaliatory tickle!",
            " Cutlass retaliates! No quarter in tickle warfare!",
            " The Captain strikes back with ten wiggling fingers!",
            " Cutlass attempts an immediate counter-tickle!",
        ])

        text += retaliation

    return {
        "text": text,
        "tickle_back": tickle_back,
        "milestone": False,
    }
