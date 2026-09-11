"""Shared command routing constants."""

SHORT_COMMAND_ALIASES = {
    "!cutlass repair": "!cutlass ship repair",
    "!cutlass upgrades": "!cutlass ship upgrades",
    "!cutlass history": "!cutlass ship history",
    "!cutlass treasury": "!cutlass ship treasury",
    "!cutlass destinations": "!cutlass voyage destinations",
}

STORY_COMMANDS = frozenset({
    "!cutlass story",
    "!c story",
})

PUNBATTLE_COMMANDS = frozenset({
    "!cutlass punbattle",
    "!c punbattle",
})
