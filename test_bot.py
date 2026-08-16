"""Self-check for the pure logic. Run: .venv/bin/python test_bot.py"""
import asyncio
import re
from datetime import datetime, timezone
from types import SimpleNamespace

import assistant
import config
import main
import roster
from cogs import batch, helpdesk


class FakeMember:
    def __init__(self, *role_names):
        self.id = 42
        self.roles = [SimpleNamespace(name=n) for n in ("@everyone",) + role_names]

    def __str__(self):
        return "aryan#1"


# --- knowledge base ---------------------------------------------------------

def test_knowledge_loads():
    kb = assistant.relevant_knowledge("how do I verify my account?")
    assert "### verification" in kb, "knowledge/*.md not picked up"
    assert "!verify" in kb


def test_retrieval_shrinks_the_prompt():
    """The whole point: one question must not ship the entire knowledge base."""
    everything = sum(
        p.stat().st_size for p in assistant.config.KNOWLEDGE_DIR.glob("*.md")
    )
    picked = len(assistant.relevant_knowledge("where do I do my laundry?"))
    assert picked < everything / 4, f"retrieval sent {picked} of {everything} bytes"


def test_budget_is_never_exceeded():
    """The cap is what keeps us inside Groq's per-minute token limit."""
    questions = "fee hostel club event campus intern academic verify batch role curfew mess wifi exam attendance".split()
    worst = max(len(assistant.relevant_knowledge(q)) for q in questions)
    assert worst <= assistant.MAX_KNOWLEDGE_CHARS, f"sent {worst} chars"


def test_fee_question_reaches_the_numbers():
    """Regression: the fee table lives under a heading that says neither 'fee' nor 'much'."""
    got = assistant.relevant_knowledge("how much are the hostel fees?")
    assert re.search(r"1,1[0-9],[0-9]{3}", got), "retrieved fee text without the figures"


def test_small_talk_retrieves_nothing():
    """Greetings must not drag in documentation -- that was pure wasted budget."""
    for greeting in ("hey!", "how are you?", "lol thanks"):
        assert assistant.relevant_knowledge(greeting) == "", greeting


def test_empty_knowledge_still_builds_a_prompt():
    msgs = assistant.build_messages("hi", "", "FACTS")
    assert "nothing in the NST reference" in msgs[1]["content"]


def test_retrieval_picks_right_doc():
    """If retrieval starts picking wrong, it shows up here before it shows up in Discord."""
    expected = {
        "how do I verify my account?": "verification",
        "what document do I need to submit?": "verification",
        "how do I join a club?": "clubs",
        "how much is the hostel fee?": "fees",
        "what time is curfew in the hostel?": "hostel",
        "where can I ask about internships?": "internships",
        "how does attendance work?": "academics",
        "when is the next fest?": "events",
        "how do I get my year role?": "academics",  # where !batch is documented
    }
    for question, doc in expected.items():
        got = assistant.relevant_knowledge(question)
        assert f"### {doc}" in got, f"{question!r} -> missed {doc}.md"


# --- user facts fed to the model --------------------------------------------

def test_never_submitted():
    facts = assistant.describe_user(FakeMember("Unverified"), None, None)
    assert "never submitted" in facts
    assert "has not run !batch" in facts
    assert "Unverified" in facts
    assert "@everyone" not in facts


def test_pending_shows_date():
    facts = assistant.describe_user(
        FakeMember("Unverified"),
        {"status": "pending", "submitted_at": datetime(2026, 8, 11)},
        None,
    )
    assert "pending" in facts and "11 August 2026" in facts


def test_rejected_shows_reason():
    facts = assistant.describe_user(
        FakeMember("Unverified"),
        {"status": "rejected", "submitted_at": datetime(2026, 8, 11), "reason": "blurry scan"},
        None,
    )
    assert "blurry scan" in facts


def test_batch_facts():
    facts = assistant.describe_user(
        FakeMember("Confirmed Student", "2nd Year"),
        {"status": "approved", "submitted_at": datetime(2026, 8, 1)},
        {"name": "Aryan", "admission_year": 2024, "assigned_role": "2nd Year"},
    )
    assert "admission year 2024" in facts and "2nd Year" in facts


def test_prompt_carries_everything():
    msgs = assistant.build_messages("what year am I?", "KB HERE", "FACTS HERE")
    assert msgs[0]["role"] == "system" and "only" in msgs[0]["content"].lower()
    assert "KB HERE" in msgs[1]["content"]
    assert "FACTS HERE" in msgs[1]["content"]
    assert "what year am I?" in msgs[1]["content"]


# --- URN / year mapping -----------------------------------------------------

def test_academic_year_rolls_over_in_july():
    jun = datetime(2026, 6, 30, tzinfo=timezone.utc)
    jul = datetime(2026, 7, 1, tzinfo=timezone.utc)
    assert batch.current_academic_year(jun) == 2025
    assert batch.current_academic_year(jul) == 2026


def test_parse_urn():
    assert batch.parse_urn("2024-B-123456789B") == 2024
    assert batch.parse_urn(" 2024-b-1234 ") == 2024
    assert batch.parse_urn("abcd-B-1234") is None, "non-numeric year must be rejected"
    assert batch.parse_urn("2024") is None, "too short must be rejected"


def test_year_role_mapping():
    sep2026 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert batch.year_role_for(2026, sep2026) == "Freshers"
    assert batch.year_role_for(2025, sep2026) == "2nd Year"
    assert batch.year_role_for(2023, sep2026) == "4th Year"
    assert batch.year_role_for(2022, sep2026) is None, "5th year has no role"
    assert batch.year_role_for(2027, sep2026) is None, "future admission has no role"


# --- mention parsing --------------------------------------------------------

def test_mention_stripping():
    """The bot may have a server nickname, so only the raw <@id> token is reliable."""
    bot = SimpleNamespace(user=SimpleNamespace(id=999, name="NST-Bot"))
    cog = helpdesk.Helpdesk.__new__(helpdesk.Helpdesk)
    cog.bot = bot

    asked = []

    async def fake_respond(channel, author, question):
        asked.append(question)

    cog.respond = fake_respond

    for raw in ("<@999> how do I verify?", "<@!999>  how do I verify?", "how do I verify? <@999>"):
        msg = SimpleNamespace(content=raw, channel=None, author=None)
        asyncio.run(cog.handle_mention(msg))

    assert asked == ["how do I verify?"] * 3, asked


# --- roster matching --------------------------------------------------------

def _row(name, tokens=None):
    key = roster.normalize_name(name)
    return {"name": name, "name_key": key, "name_tokens": tokens or len(key.split())}


def test_urn_normalization_is_forgiving():
    """However a student types it, it has to reach the same key the importer wrote."""
    canonical = roster.normalize_urn("2024-B-13072005B")
    for typed in ("2024-b-13072005b", "2024 B 13072005 B", "2024B13072005B"):
        assert roster.normalize_urn(typed) == canonical, typed


def test_urn_shape_is_checked_before_the_database():
    assert roster.looks_like_urn("2024-B-13072005B")
    assert roster.looks_like_urn("2024-B-26102005"), "suffix is optional"
    for bad in ("", "hello", "2024-B-123", "24-B-13072005B"):
        assert not roster.looks_like_urn(bad), bad


def test_name_scoring_tolerates_real_variation():
    row = _row("Manthan Subhash Ziman")
    assert roster.score_name("Manthan Subhash Ziman", row) == 100
    assert roster.score_name("manthan  subhash ziman", row) == 100, "case and spacing"
    assert roster.score_name("Ziman Manthan Subhash", row) == 100, "word order"
    assert roster.score_name("Priyank Gaur", row) < config.NAME_MATCH_REVIEW


def test_single_word_names_never_auto_approve_on_a_fuzzy_match():
    """'Neha' vs 'Neel' scores high but they are two different students."""
    row = _row("Neha")
    assert roster.decide(roster.score_name("Neha", row), row) == roster.AUTO
    assert roster.decide(89, row) != roster.AUTO


def test_decide_thresholds():
    row = _row("Priyank Gaur")
    assert roster.decide(100, row) == roster.AUTO
    assert roster.decide(config.NAME_MATCH_AUTO, row) == roster.AUTO
    assert roster.decide(config.NAME_MATCH_AUTO - 1, row) == roster.REVIEW
    assert roster.decide(config.NAME_MATCH_REVIEW - 1, row) == roster.REJECT


def test_suggest_only_mode_never_auto_approves():
    row = _row("Priyank Gaur")
    original = config.ROSTER_AUTO_APPROVE
    try:
        config.ROSTER_AUTO_APPROVE = False
        assert roster.decide(100, row) == roster.REVIEW
    finally:
        config.ROSTER_AUTO_APPROVE = original


# --- wiring -----------------------------------------------------------------

def test_all_cogs_load():
    async def load():
        bot = main.build_bot()
        for name in main.COGS:
            await bot.load_extension(f"cogs.{name}")
        return bot

    bot = asyncio.run(load())
    assert set(main.COGS) <= {c.lower() for c in bot.cogs}
    for name in ("verify", "approve", "reject", "batch", "ask", "ping"):
        assert bot.get_command(name), f"command !{name} disappeared"


if __name__ == "__main__":
    for name, fn in sorted(vars().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("all passed")
