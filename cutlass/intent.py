import re


def detect_direct_question_mode(message):
    """
    Detect clear direct questions addressed to Captain that should be
    answered before unrelated memories or creator callbacks.
    """

    content = message.content.lower().strip()

    question_patterns = [
        r"\bare you\b",
        r"\bdo you\b",
        r"\bdid you\b",
        r"\bhave you\b",
        r"\bwould you\b",
        r"\bcould you\b",
        r"\bcan you\b",
        r"\bwhat do you\b",
        r"\bwhat would you\b",
        r"\bwhat are you\b",
        r"\bwhat is your\b",
        r"\bwhat's your\b",
        r"\bwho are you\b",
        r"\bwho is your\b",
        r"\bwhy do you\b",
        r"\bwhy are you\b",
        r"\bhow are you\b",
        r"\bhow would you\b",
        r"\breckon you\b",
    ]

    for pattern in question_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True

    return content.endswith("?")


def detect_humor_mode(message):
    """
    Deterministically classify humor and playful hypothetical messages.

    Special conversational humor must be identified before broad
    direct-question/gameplay routing.
    """

    content = message.content.lower().strip()

    # --------------------------------------------------------
    # Targeted jokes / roasts
    # --------------------------------------------------------

    targeted_patterns = [
        r"\bmake\s+(?:me\s+)?(?:a\s+)?joke\s+about\b",
        r"\btell\s+(?:me\s+)?(?:a\s+)?joke\s+about\b",
        r"\bjoke\s+about\b",
        r"\broast\b",
        r"\btease\b",
        r"\bmake\s+fun\s+of\b",
    ]

    for pattern in targeted_patterns:
        if re.search(
            pattern,
            content,
            re.IGNORECASE
        ):
            return "TARGETED_JOKE_REQUEST"

    # --------------------------------------------------------
    # Explicit humor requests
    #
    # Supports adjective-bearing requests such as:
    #   "Tell me a pirate joke"
    #   "Give me an old man joke"
    # --------------------------------------------------------

    humor_request_patterns = [
        r"\bgive\s+(?:me\s+)?(?:a\s+)?pun\b",
        r"\btell\s+(?:me\s+)?(?:a\s+)?pun\b",
        r"\bpun\s+(?:pls|please)\b",

        r"\bgive\s+(?:me\s+)?(?:a\s+)?joke\b",
        r"\btell\s+(?:me\s+)?(?:a\s+)?joke\b",

        r"\bgive\s+(?:me\s+)?(?:an?\s+)?(?:[\w'-]+\s+){0,4}joke\b",
        r"\btell\s+(?:me\s+)?(?:an?\s+)?(?:[\w'-]+\s+){0,4}joke\b",

        r"\bmake\s+(?:me\s+)?laugh\b",

        r"\bgive\s+(?:me\s+)?(?:a\s+)?one[- ]liner\b",
        r"\btell\s+(?:me\s+)?(?:a\s+)?one[- ]liner\b",
    ]

    for pattern in humor_request_patterns:
        if re.search(
            pattern,
            content,
            re.IGNORECASE
        ):
            return "HUMOR_REQUEST"

    # --------------------------------------------------------
    # Jokes being told TO Captain
    # --------------------------------------------------------

    joke_signals = [
        r"\bwhy did\b",
        r"\bwhat do you call\b",
        r"\bwhat did\b",
        r"\bwalks into\b",
        r"\bknock knock\b",
        r"\btherefore\b.*\bar+r+\b",
        r"\bar+r+\b.*\bar+r+\b",
    ]

    for pattern in joke_signals:
        if re.search(
            pattern,
            content,
            re.IGNORECASE
        ):
            return "JOKE_TOLD_TO_CAPTAIN"

    # --------------------------------------------------------
    # "Who would/will win?" and matchup questions
    #
    # These are conversation, NOT Ship World combat requests.
    # --------------------------------------------------------

    matchup_patterns = [
        r"\bwho\s+(?:would|will)\s+win\b",
        r"\bwho\s+wins\b",

        r"\b(?:which|what)\s+"
        r"(?:one|side|team|creature|monster|character)"
        r"\s+(?:would|will)\s+win\b",

        r"\bwould\s+.+?\s+"
        r"(?:beat|defeat|win\s+against)\s+.+?"
        r"(?:\?|$)",
    ]

    for pattern in matchup_patterns:
        if re.search(
            pattern,
            content,
            re.IGNORECASE
        ):
            return "PLAYFUL_HYPOTHETICAL"

    # Explicit versus / against scenarios involving a contest.
    versus_matchup = (
        re.search(
            r"\b(?:vs\.?|versus|against)\b",
            content,
            re.IGNORECASE
        )
        and re.search(
            r"\b(?:"
            r"win|wins|fight|battle|wrestl\w*|"
            r"race|contest|match|beat|defeat"
            r")\b",
            content,
            re.IGNORECASE
        )
    )

    if versus_matchup:
        return "PLAYFUL_HYPOTHETICAL"

    # --------------------------------------------------------
    # Explicit hypothetical constructions
    # --------------------------------------------------------

    hypothetical_markers = (
        "hypothetically",
        "hypothetical",
        "what if ",
        "what happens if ",
        "what would happen if ",
        "what would you do if",
        "what would ye do if",
        "if you became",
        "if ye became",
        "if you were",
        "if ye were",
        "how would you ",
        "how would ye ",
        "imagine you ",
        "imagine ye ",
        "imagine if ",
        "suppose you ",
        "suppose ye ",
        "suppose if ",
    )

    if any(
        marker in content
        for marker in hypothetical_markers
    ):
        return "PLAYFUL_HYPOTHETICAL"

    # Questions about Captain/Barnacle/pirates in an imaginary
    # conditional situation should remain conversational even when
    # the subject happens to include identity-related words.
    fictional_subject = re.search(
        r"\b(?:"
        r"captain\s+cutlass|cutlass|captain|"
        r"barnacle|parrot|pirate"
        r")\b",
        content,
        re.IGNORECASE
    )

    conditional_question = (
        "?" in content
        and re.search(
            r"\b(?:would|could|might)\b",
            content,
            re.IGNORECASE
        )
        and re.search(
            r"\bif\b",
            content,
            re.IGNORECASE
        )
    )

    if fictional_subject and conditional_question:
        return "PLAYFUL_HYPOTHETICAL"

    return "NORMAL"


def is_member_profile_request(message, bot_user_id=None):
    """
    Return True only when the current message explicitly asks
    Captain for information, knowledge, or an opinion about a
    Discord member.

    A member mention by itself is NOT a profile request.
    """

    content = message.content.strip()
    lowered = content.lower()

    if bot_user_id is not None:
        content = re.sub(
            rf"<@!?{bot_user_id}>",
            "",
            content
        ).strip()
        lowered = content.lower()

    gameplay_subject_pattern = (
        r"\b(?:about|of)\s+(?:the\s+|our\s+|this\s+)?"
        r"(?:"
        r"voyage|voyages|ship|living\s+ship|hull|battle|battles|"
        r"fight|combat|monster|monsters|boss|bosses|island|islands|"
        r"world|world\s+history|history|jobs|job|crew\s+work|"
        r"commands?|doubloons?|treasury|treasure|exploration"
        r")\b"
    )

    if re.search(
        gameplay_subject_pattern,
        lowered,
        flags=re.IGNORECASE
    ):
        return False

    patterns = (
        r"\bwhat\s+do\s+you\s+think\s+(?:about|of)\b",
        r"\bwhat\s+do\s+you\s+know\s+about\b",
        r"\btell\s+me\s+(?:something|anything|a\s+few\s+words)\s+about\b",
        r"\bsay\s+(?:something|anything|a\s+few\s+words)\s+about\b",
        r"\btell\s+me\s+about\b",
    )

    return any(
        re.search(
            pattern,
            content,
            flags=re.IGNORECASE
        )
        for pattern in patterns
    )
