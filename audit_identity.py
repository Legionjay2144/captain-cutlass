#!/usr/bin/env python3

import argparse
import re
import sqlite3
from collections import defaultdict


DB_PATH = "/app/data/captain.db"


# ---------------------------------------------------------
# Pronoun detection
#
# These patterns only identify potentially gendered member
# references. They do NOT automatically mean a record is bad.
# ---------------------------------------------------------

HE_PATTERN = re.compile(
    r"\b(?:he|him|his|himself)\b",
    re.I
)

SHE_PATTERN = re.compile(
    r"\b(?:she|her|hers|herself)\b",
    re.I
)


# ---------------------------------------------------------
# Obvious non-member references that should not trigger an
# automatic fix merely because they contain pronouns.
# ---------------------------------------------------------

NON_MEMBER_HINTS = (
    "captain cutlass",
    "captain himself",
    "captain is",
    "captain was",
    "old pirate",
    "the pirate",
    "a pirate",
    "barnacle",
    "parrot",
    "old salt",
    "the ship",
    "ship was",
    "ship is",
    "descartes",
)


def clean_text(value):
    return str(value or "").strip()


def normalize_pronouns(value):
    value = clean_text(value).casefold()

    value = re.sub(
        r"\s+",
        "",
        value
    )

    return value


def profile_allows_text(
    pronouns,
    text
):
    """
    Check stored explicit pronouns against gendered words.

    Gender is deliberately ignored here because gender does
    not establish pronouns.
    """

    pronouns = normalize_pronouns(
        pronouns
    )

    has_he = bool(
        HE_PATTERN.search(text)
    )

    has_she = bool(
        SHE_PATTERN.search(text)
    )

    if not pronouns:
        return not (
            has_he
            or has_she
        )

    if pronouns == "he/him":
        return not has_she

    if pronouns == "she/her":
        return not has_he

    if pronouns == "they/them":
        return not (
            has_he
            or has_she
        )

    # Unknown/custom pronouns do not authorize binary
    # pronouns automatically.
    return not (
        has_he
        or has_she
    )


def likely_non_member_reference(
    username,
    text
):
    """
    Conservative false-positive filter.

    If a gendered sentence clearly refers to Captain,
    Barnacle, a generic pirate, or ship lore instead of the
    profile owner, leave it alone.
    """

    lowered = text.casefold()

    username = clean_text(
        username
    ).casefold()

    if username and username in lowered:
        return False

    for hint in NON_MEMBER_HINTS:
        if hint in lowered:
            return True

    return False


def neutralize_member_pronouns(
    username,
    text
):
    """
    Conservative deterministic neutralizer.

    This is intentionally simple. It only changes obvious
    third-person pronouns and preserves the rest of the text.
    """

    text = clean_text(
        text
    )

    replacements = (
        (r"\bHe is\b", f"{username} is"),
        (r"\bHe was\b", f"{username} was"),
        (r"\bHe's\b", f"{username} is"),
        (r"\bhe's\b", f"{username} is"),
        (r"\bShe is\b", f"{username} is"),
        (r"\bShe was\b", f"{username} was"),
        (r"\bShe's\b", f"{username} is"),
        (r"\bshe's\b", f"{username} is"),
        (r"\bHe\b", username),
        (r"\bhe\b", username),
        (r"\bShe\b", username),
        (r"\bshe\b", username),
        (r"\bhimself\b", "themself"),
        (r"\bherself\b", "themself"),
        (r"\bhim\b", "them"),
        (r"\bher\b", "them"),
        (r"\bhis\b", "their"),
        (r"\bhers\b", "theirs"),
    )

    result = text

    for pattern, replacement in replacements:
        result = re.sub(
            pattern,
            replacement,
            result
        )

    result = re.sub(
        r"\s+",
        " ",
        result
    ).strip()

    return result


def load_profiles(db):

    rows = db.execute("""
        SELECT
            guild_id,
            user_id,
            username,
            gender,
            pronouns
        FROM user_profiles
    """).fetchall()

    return {
        (
            row["guild_id"],
            row["user_id"]
        ): row
        for row in rows
    }


def audit_table(
    db,
    profiles,
    table,
    id_column,
    text_column,
):

    findings = []

    rows = db.execute(
        f"""
        SELECT *
        FROM {table}
        WHERE {text_column} IS NOT NULL
          AND TRIM({text_column}) != ''
        """
    ).fetchall()

    for row in rows:

        key = (
            row["guild_id"],
            row["user_id"]
        )

        profile = profiles.get(
            key
        )

        if profile is None:
            continue

        text = clean_text(
            row[text_column]
        )

        if not (
            HE_PATTERN.search(text)
            or SHE_PATTERN.search(text)
        ):
            continue

        if profile_allows_text(
            profile["pronouns"],
            text
        ):
            continue

        if likely_non_member_reference(
            profile["username"],
            text
        ):
            continue

        findings.append({
            "table": table,
            "id_column": id_column,
            "id": row[id_column],
            "text_column": text_column,
            "text": text,
            "guild_id": row["guild_id"],
            "user_id": row["user_id"],
            "username": profile["username"],
            "gender": profile["gender"],
            "pronouns": profile["pronouns"],
        })

    return findings


def audit_relationships(
    db,
    profiles
):

    findings = []

    rows = db.execute("""
        SELECT *
        FROM relationships
    """).fetchall()

    for row in rows:

        key = (
            row["guild_id"],
            row["user_id"]
        )

        profile = profiles.get(
            key
        )

        if profile is None:
            continue

        for column in (
            "nickname",
            "opinion"
        ):

            text = clean_text(
                row[column]
            )

            if not text:
                continue

            if not (
                HE_PATTERN.search(text)
                or SHE_PATTERN.search(text)
            ):
                continue

            if profile_allows_text(
                profile["pronouns"],
                text
            ):
                continue

            if likely_non_member_reference(
                profile["username"],
                text
            ):
                continue

            findings.append({
                "table": "relationships",
                "id_column": None,
                "id": None,
                "text_column": column,
                "text": text,
                "guild_id": row["guild_id"],
                "user_id": row["user_id"],
                "username": profile["username"],
                "gender": profile["gender"],
                "pronouns": profile["pronouns"],
            })

    return findings


def print_report(
    findings
):

    grouped = defaultdict(list)

    for finding in findings:

        grouped[
            (
                finding["guild_id"],
                finding["user_id"],
                finding["username"],
                finding["gender"],
                finding["pronouns"],
            )
        ].append(
            finding
        )

    print()
    print("CAPTAIN CUTLASS IDENTITY AUDIT")
    print("=" * 60)

    if not findings:
        print()
        print("No unsafe member-identity records detected.")
        return

    for (
        guild_id,
        user_id,
        username,
        gender,
        pronouns,
    ), items in sorted(
        grouped.items(),
        key=lambda item: (
            str(item[0][2]).casefold(),
            item[0][0],
        )
    ):

        print()
        print("-" * 60)
        print("Member:", username)
        print("Guild:", guild_id)
        print("User ID:", user_id)
        print(
            "Gender:",
            gender or "UNKNOWN"
        )
        print(
            "Pronouns:",
            pronouns or "UNKNOWN"
        )
        print(
            "Unsafe records:",
            len(items)
        )

        for item in items:

            location = (
                item["table"]
                + "."
                + item["text_column"]
            )

            if item["id"] is not None:
                location += (
                    " #"
                    + str(item["id"])
                )

            print()
            print(" ", location)
            print("   ", item["text"])

    print()
    print("=" * 60)
    print(
        "TOTAL UNSAFE MEMBER RECORDS:",
        len(findings)
    )


def fix_findings(
    db,
    findings
):

    changed = 0

    for item in findings:

        username = (
            item["username"]
            or "This crewmate"
        )

        new_text = neutralize_member_pronouns(
            username,
            item["text"]
        )

        if (
            not new_text
            or new_text == item["text"]
        ):
            print(
                "SKIPPED:",
                item["table"],
                item["id"],
                repr(item["text"])
            )
            continue

        if item["table"] == "relationships":

            db.execute(
                f"""
                UPDATE relationships
                SET {item["text_column"]} = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                  AND user_id = ?
                """,
                (
                    new_text,
                    item["guild_id"],
                    item["user_id"],
                )
            )

        else:

            db.execute(
                f"""
                UPDATE {item["table"]}
                SET {item["text_column"]} = ?
                WHERE {item["id_column"]} = ?
                  AND guild_id = ?
                  AND user_id = ?
                """,
                (
                    new_text,
                    item["id"],
                    item["guild_id"],
                    item["user_id"],
                )
            )

        changed += 1

        print()
        print(
            "FIXED:",
            item["table"],
            item["id"]
        )
        print(
            " OLD:",
            item["text"]
        )
        print(
            " NEW:",
            new_text
        )

    db.commit()

    print()
    print(
        "TOTAL RECORDS FIXED:",
        changed
    )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Audit Captain Cutlass persistent data for "
            "member-gender/pronoun assumptions."
        )
    )

    parser.add_argument(
        "--db",
        default=DB_PATH,
        help="SQLite database path"
    )

    parser.add_argument(
        "--fix",
        action="store_true",
        help=(
            "Neutralize records detected as unsafe. "
            "Default mode is read-only."
        )
    )

    args = parser.parse_args()

    db = sqlite3.connect(
        args.db
    )

    db.row_factory = sqlite3.Row

    profiles = load_profiles(
        db
    )

    findings = []

    findings.extend(
        audit_table(
            db,
            profiles,
            "user_memories",
            "id",
            "memory",
        )
    )

    findings.extend(
        audit_table(
            db,
            profiles,
            "running_jokes",
            "id",
            "joke",
        )
    )

    findings.extend(
        audit_table(
            db,
            profiles,
            "relationship_events",
            "id",
            "event",
        )
    )

    findings.extend(
        audit_relationships(
            db,
            profiles
        )
    )

    print_report(
        findings
    )

    if args.fix:

        if not findings:
            return

        print()
        print(
            "FIX MODE ENABLED"
        )

        fix_findings(
            db,
            findings
        )

    db.close()


if __name__ == "__main__":
    main()
