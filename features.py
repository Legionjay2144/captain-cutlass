import random
from datetime import datetime
from zoneinfo import ZoneInfo


MOODS = [
    "cheerful",
    "grumpy",
    "sleepy",
    "suspicious",
    "nostalgic",
    "pun-crazed",
    "dramatic",
    "mischievous"
]


WISDOM = [
    "Never trust a calm sea, an empty tavern, or a pirate offering free financial advice.",
    "A good map gets ye to treasure. A bad map gets ye a story.",
    "If ye cannot fix it with rope, ye probably are not using enough rope.",
    "The early bird gets the worm. The old pirate waits for breakfast.",
    "Age brings wisdom. Unfortunately, it also brings suspicious noises when standing up.",
    "Treasure comes and goes. A good chair with proper back support is forever.",
    "Any problem can be solved with patience, experience, or pretending ye did not hear it.",
    "A pirate who says they have never been lost is either lying or still lost."
]


REACTIONS = [
    "\U0001f3f4\u200d\u2620\ufe0f",
    "\U0001f602",
    "\U0001f440",
    "\U0001f480",
    "\u2693"
]


WELCOME_MESSAGES = {

    "cheerful": [
        "Ahoy {member}! Welcome aboard! Grab a hammock and make yerself at home!",
        "Welcome aboard, {member}! Always good to see a fresh face on deck!",
        "Ahoy {member}! Ye've joined the crew! May yer adventures be grand and yer troubles stay ashore!",
        "Well blow me down, {member} has joined the crew! Welcome aboard!",
        "Welcome, {member}! Another fine soul aboard means one more person to blame when something goes overboard!"
    ],

    "grumpy": [
        "Oh wonderful, another crewmate. Welcome aboard, {member}. Try not to break anything.",
        "Who let {member} aboard? Ah well, welcome to the crew!",
        "Welcome aboard, {member}. Keep the noise down, some of us have important napping to do.",
        "Aye, welcome {member}. I'd get up to greet ye, but me knees have filed a formal complaint.",
        "Another one? Fine. Welcome aboard, {member}. Hammocks are below deck."
    ],

    "sleepy": [
        "Eh? What? Oh... welcome aboard, {member}. Wake me if we hit something.",
        "Welcome aboard, {member}. I'd give ye the grand tour, but I was halfway through a magnificent nap.",
        "Ahoy {member}... or goodnight... whichever one we're doing.",
        "Welcome, {member}. Find a hammock. I highly recommend 'em.",
        "A new crewmate? Welcome aboard, {member}. Now somebody wake me when dinner's ready."
    ],

    "suspicious": [
        "Hmm... {member}, is it? Welcome aboard. I'll be keeping me good eye on ye.",
        "A new face aboard the ship! Welcome, {member}. Ye wouldn't happen to know anything about missing treasure, would ye?",
        "Welcome aboard, {member}. Kindly declare all treasure, parrots, and suspicious barrels.",
        "Ahoy {member}. Welcome aboard... but if me rum disappears, I know who I'm questioning first.",
        "Welcome, {member}. Ye seem trustworthy enough... which makes me suspicious."
    ],

    "nostalgic": [
        "Welcome aboard, {member}. Reminds me of when I first took to sea... though I had considerably better knees then.",
        "Ahoy {member}! Every old crew starts with a new face. Welcome aboard.",
        "Welcome, {member}. Many good stories begin with someone stepping aboard for the first time.",
        "A new crewmate! Welcome aboard, {member}. Takes me back to me younger days... sometime around the invention of dirt.",
        "Welcome aboard, {member}. Here's hoping ye make a few stories worth remembering."
    ],

    "pun-crazed": [
        "Ahoy {member}! Welcome aboard! I hope ye find the experience oar-some!",
        "Welcome, {member}! Don't worry if ye feel lost, we'll help ye get yer sea legs!",
        "Ahoy {member}! Glad ye could dock around and join us!",
        "Welcome aboard, {member}! Things are looking ship-shape already!",
        "Ahoy {member}! Welcome to the crew. We hope ye have a ferry good time!"
    ],

    "dramatic": [
        "ALL HANDS ON DECK! {member} has arrived! Let the chronicles record this glorious day!",
        "Sound the bells! Raise the colors! {member} has joined the crew!",
        "From beyond the horizon comes {member}! Welcome aboard, brave traveler!",
        "The winds have delivered us another soul! Welcome aboard, {member}!",
        "Mark this day in the ship's log! {member} has officially joined the crew!"
    ],

    "mischievous": [
        "Welcome aboard, {member}! Nobody tell 'em about the incident below deck.",
        "Ahoy {member}! Welcome to the crew. If anyone asks, ye've never seen me before.",
        "Welcome, {member}! First rule aboard this ship: Captain Cutlass was nowhere near it.",
        "Ahoy {member}! Welcome aboard. We've already assigned ye partial responsibility for whatever happens next.",
        "Welcome aboard, {member}! Ye arrived just in time to become an accomplice."
    ],

    "default": [
        "Ahoy {member}! Welcome aboard!",
        "Welcome aboard, {member}! Glad to have ye among the crew!",
        "Ahoy {member}! Pull up a hammock and make yerself at home!",
        "Welcome to the crew, {member}! Mind yer head and watch yer step!",
        "Another crewmate aboard! Welcome, {member}!"
    ]
}


def random_wisdom():

    return random.choice(
        WISDOM
    )


def choose_reaction():

    return random.choice(
        REACTIONS
    )


def get_welcome_message(
    member_mention,
    mood="cheerful"
):

    mood = (
        mood
        .strip()
        .lower()
    )

    messages = WELCOME_MESSAGES.get(
        mood,
        WELCOME_MESSAGES["default"]
    )

    return random.choice(
        messages
    ).format(
        member=member_mention
    )


def relationship_for_familiarity(
    familiarity
):

    if familiarity >= 100:
        return "Old Salt"

    if familiarity >= 75:
        return "Trusted Crewmate"

    if familiarity >= 50:
        return "Familiar Crewmate"

    if familiarity >= 25:
        return "Regular Crewmate"

    return "New Crewmate"


def milestone_for_familiarity(
    old_value,
    new_value
):

    for milestone in (
        25,
        50,
        75,
        100
    ):

        if (
            old_value < milestone
            <= new_value
        ):
            return milestone

    return None


def within_quiet_hours(
    start_hour,
    end_hour,
    timezone_name
):

    try:

        timezone = ZoneInfo(
            timezone_name
        )

    except Exception:

        timezone = ZoneInfo(
            "UTC"
        )

    hour = datetime.now(
        timezone
    ).hour

    if start_hour == end_hour:
        return False

    if start_hour < end_hour:

        return (
            start_hour
            <= hour
            < end_hour
        )

    return (
        hour >= start_hour
        or hour < end_hour
    )