"""The AI help-desk layer: knowledge lookup, prompt assembly, Groq call.

Deliberately read-only. Nothing here touches roles or verification records, so a bad
model output can only ever produce a wrong sentence, never a wrong permission.
"""
import re
from collections import Counter
from math import log

import aiohttp

import config
import db

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are NST-Bot, the help desk for the NST college Discord server.
You're warm and casual — like a friendly senior helping out a junior, not a corporate
FAQ page.

TONE
- Talk like a person: contractions, plain words, the odd emoji.
- Small talk ("hi", "how are you", "thanks") gets a short, friendly reply of one or
  two sentences. Just answer it. Don't announce that you're a bot, don't explain what
  you can't do, and don't pivot into a list of your features unless they ask.
- Real questions get a helpful answer in under 6 sentences. No markdown headings.

FACTS
- Answer NST questions using ONLY the reference below. If the answer isn't in it, say
  you don't know and point them to a server admin. Never invent NST facts, dates,
  fees, contacts, or channel names.

THE ASKER'S RECORD
- Their roles and verification details are private background, not conversation
  material. Use them only when they're directly relevant to what was asked.
- When they DO ask about their own status, batch, or roles, give them the specifics
  from their record — status, the date they submitted, the rejection reason. That's
  the whole point of having it. Being vague there is unhelpful.
- Never bring up someone's roles, verification status, batch, or rejection reason on
  your own. These channels are public — announcing that kind of thing unprompted is
  embarrassing for them. If they didn't ask about it, don't mention it.

ACTIONS
- You can't do anything: no verifying, approving, rejecting, or changing roles. If
  someone asks, tell them warmly which command or which admin handles it."""


STOPWORDS = frozenset(
    """the and for are can you your его how what where when who why does did with
    from this that they them there here about into out get got has have had was were
    will would should could not but any all one some more most only own same than too
    very just now also which while their our his her its it's i'm dont don't""".split()
)


def _words(text):
    """Content words, crudely stemmed to their first 5 letters.

    The stem is what makes "verify" match a doc full of "verification"; without it a
    question and its answer can share a topic and no literal word.
    """
    return [w[:5] for w in re.findall(r"[a-z']{3,}", text.lower()) if w not in STOPWORDS]


def _sections():
    """Every '## ' section of every knowledge file, as (label, text).

    Sections rather than whole files: a question about fees needs the fee table, not
    all of fees.md, hostel.md and campus.md.
    """
    out = []
    for path in sorted(config.KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for part in re.split(r"\n(?=##\s)", text):
            part = part.strip()
            if not part:
                continue
            heading = part.splitlines()[0].lstrip("# ").strip()
            out.append((f"{path.stem} / {heading}", part))
    return out


MAX_KNOWLEDGE_CHARS = 4500  # ~1100 tokens; keeps us well inside Groq's free-tier TPM


def relevant_knowledge(question, budget=MAX_KNOWLEDGE_CHARS):
    """The best-matching knowledge sections that fit inside a character budget.

    Budget rather than a fixed section count: sections vary in size, and this bounds
    the prompt no matter how much the knowledge folder grows.

    Returns "" when nothing is relevant, so small talk costs no knowledge tokens.

    ponytail: TF-IDF over a few dozen short sections, recomputed per question. No
    embeddings, no vector store, no index to rebuild -- dropping a .md in the folder
    is the whole ingestion step. Upgrade to an embedding retriever when questions and
    docs stop sharing words at all (paraphrase, synonyms); the retrieval tests are
    where that failure surfaces first.
    """
    sections = _sections()
    if not sections:
        return ""

    counts = [Counter(_words(text)) for _, text in sections]
    doc_freq = Counter(word for c in counts for word in c)
    asked = set(_words(question))
    n = len(sections)

    def score(i):
        c = counts[i]
        # Damped term frequency, so a section that keeps saying the word beats one
        # that mentions it once; IDF, so a word common to everything counts little.
        return sum(
            (1 + log(c[word])) * log(n / doc_freq[word] + 1) for word in asked if c[word]
        )

    def rendered(i):
        return f"### {sections[i][0]}\n{sections[i][1]}"

    picked, used = [], 0
    for i in sorted(range(n), key=score, reverse=True):
        if score(i) <= 0:
            break  # nothing relevant left; small talk stops here with picked empty
        cost = len(rendered(i)) + 2  # +2 for the blank line between sections
        if used + cost > budget:
            continue  # too big for what's left, but a smaller section may still fit
        picked.append(i)
        used += cost

    return "\n\n".join(rendered(i) for i in sorted(picked))


def describe_user(member, verification, batch):
    """One fact per line: what the server actually knows about this member."""
    facts = [f"Discord name: {member}"]
    roles = [r.name for r in member.roles if r.name != "@everyone"]
    facts.append(f"Roles: {', '.join(roles) if roles else 'none'}")

    if verification:
        line = f"Verification status: {verification['status']}"
        if verification.get("submitted_at"):
            line += f" (submitted {verification['submitted_at']:%d %B %Y})"
        if verification["status"] == "rejected" and verification.get("reason"):
            line += f", reason: {verification['reason']}"
        facts.append(line)
    else:
        facts.append("Verification status: never submitted a document")

    if batch:
        facts.append(
            f"Batch: {batch['name']}, admission year {batch['admission_year']}, "
            f"year role {batch['assigned_role']}"
        )
    else:
        facts.append("Batch: has not run !batch yet")

    return "\n".join(facts)


def build_messages(question, knowledge, user_facts):
    knowledge = knowledge or "(nothing in the NST reference matches this question)"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"NST reference:\n{knowledge}\n\n"
                f"About the person asking:\n{user_facts}\n\n"
                f"Their question: {question}"
            ),
        },
    ]


def user_facts(member):
    return describe_user(
        member,
        db.verifications.find_one(
            {"user_id": str(member.id)}, sort=[("submitted_at", -1)]
        ),
        db.batches.find_one({"user_id": str(member.id)}),
    )


async def answer(question, member):
    """Ask Groq the question, grounded in the knowledge base and the member's record."""
    payload = {
        "model": config.GROQ_MODEL,
        "messages": build_messages(
            question, relevant_knowledge(question), user_facts(member)
        ),
        "temperature": 0.3,
        "max_completion_tokens": 500,
    }
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            GROQ_ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
    return data["choices"][0]["message"]["content"].strip()[:1900]
