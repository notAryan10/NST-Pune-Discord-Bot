"""Roster lookup, and the normalization the importer and the bot must agree on.

These functions live here rather than in either caller on purpose. If the importer
normalized a URN even slightly differently from the way the bot normalizes what a
student types, every lookup would miss and the failure would look like "student not
on the roster" — the one error message nobody would think to debug.

URN first, always. The URN is unique per student; the name is not (three students in
the 2024 batch share a name with somebody else). So the URN identifies, and the name
only confirms.
"""
import re

from rapidfuzz import fuzz

import config
import db

# The college has used two URN schemes, so both have to be accepted.
#
#   2024-B-13072005B  the founding batch: admission year, campus letter, the student's
#                     date of birth as DDMMYYYY, and sometimes a trailing letter for
#                     students who share a birthday.
#   E25B070959        2025 onward: an E marker, two-digit admission year, campus
#                     letter, a two-digit programme code, and a serial. No date of
#                     birth in this one.
#   E26B07F0799       2026 adds a stream letter between the programme code and the
#                     serial, so that block is optional rather than a third pattern.
URN_PATTERNS = (
    re.compile(r"^(?P<year>\d{4})-(?P<campus>[A-Z])-(?P<dob>\d{8})(?P<suffix>[A-Z]?)$"),
    re.compile(
        r"^E(?P<yy>\d{2})(?P<campus>[A-Z])(?P<programme>\d{2})"
        r"(?P<stream>[A-Z]?)(?P<serial>\d{4})$"
    ),
)

AUTO, REVIEW, REJECT = "auto", "review", "reject"


def normalize_urn(raw):
    """Strip separators and upper-case, so '2024-b-1307 2005b' == '2024B13072005B'."""
    return re.sub(r"[^A-Z0-9]", "", (raw or "").upper())


def normalize_name(raw):
    """Lower-case, drop punctuation, collapse whitespace."""
    cleaned = re.sub(r"[^a-z\s]", " ", (raw or "").lower())
    return " ".join(cleaned.split())


def parse_urn(raw):
    """Return the admission year encoded in a URN, or None if it isn't one.

    Both schemes carry the admission year, which is all the bot needs from a URN —
    it is what the year role is derived from.
    """
    text = (raw or "").strip().upper()
    for pattern in URN_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        parts = match.groupdict()
        return int(parts["year"]) if "year" in parts else 2000 + int(parts["yy"])
    return None


def looks_like_urn(raw):
    """True if the raw input has the shape of a URN, before we hit the database."""
    return parse_urn(raw) is not None


def find(raw_urn):
    """The roster row for a URN, or None. Exact match on the unique index."""
    return db.roster.find_one({"urn": normalize_urn(raw_urn)})


def score_name(submitted, record):
    """0-100 similarity between what the student typed and the roster name.

    token_sort_ratio, so word order does not matter: "Singh Vaibhav" scores the same
    as "Vaibhav Singh", and a dropped middle name still scores well.
    """
    return int(fuzz.token_sort_ratio(normalize_name(submitted), record["name_key"]))


def decide(score, record):
    """Turn a name score into AUTO / REVIEW / REJECT.

    A single-word roster name ("Neha", "Rahul") is weak evidence — across 300-odd
    students a lone first name is close to a guess, so those never auto-approve on a
    fuzzy match alone.
    """
    if not config.ROSTER_AUTO_APPROVE:
        return REVIEW if score >= config.NAME_MATCH_REVIEW else REJECT
    if record.get("name_tokens", 0) <= 1:
        return AUTO if score == 100 else (
            REVIEW if score >= config.NAME_MATCH_REVIEW else REJECT
        )
    if score >= config.NAME_MATCH_AUTO:
        return AUTO
    return REVIEW if score >= config.NAME_MATCH_REVIEW else REJECT
