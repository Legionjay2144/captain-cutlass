import calendar
import random
from datetime import datetime

RETURN_MESSAGES = [
    "Well blow me down, {member} washed back ashore after {days} days! I was about to rent out yer hammock.",
    "Look what the tide dragged back in! Welcome back, {member}. Been {days} days, matey!",
    "{member}! There ye are! After {days} days I was beginning to think ye'd found a better ship.",
    "Ahoy {member}! Back after {days} days? I kept yer bunk mostly free of barnacles.",
]

BIRTHDAY_MESSAGES = [
    "Happy birthday, {member}! Another voyage around the sun completed. Have 50 doubloons on the Captain!",
    "All hands, raise a mug for {member}! Happy birthday! The birthday booty be 50 doubloons.",
    "Happy birthday, {member}! Ye survived another year on deck, which deserves 50 doubloons by me reckoning.",
]

def returning_message(member_mention, days):
    return random.choice(RETURN_MESSAGES).format(member=member_mention, days=days)

def birthday_message(member_mention):
    return random.choice(BIRTHDAY_MESSAGES).format(member=member_mention)

def format_birthday(month, day):
    return f"{calendar.month_name[int(month)]} {int(day)}"

def parse_birthday(text):
    text = text.strip().replace(',', '')
    for fmt in ("%B %d", "%b %d", "%m/%d", "%m-%d"):
        try:
            value = datetime.strptime(text, fmt)
            return value.month, value.day
        except ValueError:
            pass
    raise ValueError("Use a birthday like `August 23`, `Aug 23`, or `8/23`.")
