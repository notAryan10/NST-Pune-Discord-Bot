"""Import official student roster PDFs into the `roster` collection.

The source PDFs are ruled tables, so we read them with extract_tables() rather than
extract_text(). That matters: in most of these files the raw text layer has no spaces
between columns ("2024-B-10032006ADevanshuPrakash9.05..."), and splitting that back
apart is guesswork. The ruling lines give us the cell boundaries for free.

Column order is read from the header row, not assumed — the 2024 sheet leads with URN,
the 2025 elective lists lead with Name.

Only URN and name are kept. Whatever else a sheet happens to carry — SGPA, rank,
scholarship, elective, mode of study — is not verification data and does not belong in
the bot's database.

Several PDFs can be passed at once, which is how a cohort split across elective lists
gets loaded as one roster; a student appearing on two lists is imported once.

Usage:
    python scripts/import_roster.py roster.pdf                    # dry run
    python scripts/import_roster.py a.pdf b.pdf c.pdf --json out.json
    python scripts/import_roster.py roster.pdf --commit           # write to Mongo
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import roster  # noqa: E402  — needs the sys.path line above


def column_map(cells):
    """Map {'urn': i, 'name': j, 'email': k} from a header row, or None if not one.

    Email is optional but valuable: on these sheets the address is the URN plus the
    college domain, so it is a second copy of the URN that survives when the URN cell
    itself is mangled by a long name overflowing into it.
    """
    mapping = {}
    for i, cell in enumerate((c or "").strip().lower() for c in cells):
        if "email" in cell:
            mapping.setdefault("email", i)
        elif "urn" in cell:
            mapping.setdefault("urn", i)
        elif cell == "name" or cell.endswith(" name"):
            mapping.setdefault("name", i)
    return mapping if {"urn", "name"} <= mapping.keys() else None


def unmerge(cell, urn):
    """Pull the URN back out of a cell a long name has spilled into.

    When a name is too wide for its column the renderer interleaves it with the URN
    beside it — "ALI Khan" and "E25B070750" come back as "LEI 2K5hBa0n70750". The URN's
    characters are still there in order, so deleting them as a subsequence leaves
    exactly the piece of the name that overflowed.

    Returns "" unless the whole URN was consumed, so a cell that merely looks similar
    is never mistaken for a merged one.
    """
    tail, i = [], 0
    for char in cell:
        if i < len(urn) and char.upper() == urn[i]:
            i += 1
        else:
            tail.append(char)
    return "".join(tail) if i == len(urn) else ""


def parse_pdf(path):
    """Yield one dict per data row, in document order.

    The header appears on the first page only, so the column map it produces carries
    forward to every later page.
    """
    rows, columns = [], None
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):

            for table in page.extract_tables():
                for cells in table:
                    if not cells or len(cells) < 2:
                        continue

                    header = column_map(cells)
                    if header:
                        columns = header
                        continue
                    if columns is None:
                        # No header seen yet. The 2024 sheet's layout is the safer
                        # guess than silently importing a column of email addresses.
                        columns = {"urn": 0, "name": 1}

                    if max(columns.values()) >= len(cells):
                        continue
                    urn_raw = (cells[columns["urn"]] or "").strip()
                    name_raw = (cells[columns["name"]] or "").strip()
                    email = (
                        (cells[columns["email"]] or "").strip()
                        if "email" in columns
                        else ""
                    )
                    if not urn_raw and not email:
                        continue

                    # A name too long for its cell spills into the URN cell and
                    # scrambles it, which also truncates the name cell. Recover the
                    # URN from the email, then put the two halves of the name back
                    # together.
                    if email and not roster.parse_urn(urn_raw):
                        name_raw += unmerge(urn_raw, email.split("@")[0].upper())

                    rows.append(
                        {
                            "urn_raw": urn_raw,
                            "name_raw": name_raw,
                            "email": email,
                            "page": page_no,
                            "file": path.name,
                        }
                    )
    return rows


def build_records(rows, kind):
    """Turn raw rows into roster documents, separating out anything suspect.

    Returns (records, problems, overlaps). A problem is never silently dropped — an
    unimportable student is one who cannot verify, so somebody has to look at the list.
    Overlaps are different: the same student legitimately appears on two elective
    lists, so those are counted and reported, not flagged.
    """
    now = datetime.now(timezone.utc)
    records, problems, overlaps, seen = [], [], [], {}

    for row in rows:
        urn_raw, name_raw = row["urn_raw"], row["name_raw"]
        admission_year = roster.parse_urn(urn_raw)
        note = None

        # A long name can overflow its cell and scramble the URN beside it. The email
        # local part is the same URN, so fall back to it rather than losing the row.
        from_email = row.get("email", "").split("@")[0].strip()
        if admission_year is None and roster.parse_urn(from_email):
            urn_raw = from_email
            admission_year = roster.parse_urn(from_email)
            note = "URN recovered from email, name reassembled"
        elif from_email and roster.parse_urn(from_email) and roster.normalize_urn(
            from_email
        ) != roster.normalize_urn(urn_raw):
            problems.append({**row, "issue": f"URN and email disagree ({from_email})"})
            continue

        urn = roster.normalize_urn(urn_raw)
        name_key = roster.normalize_name(name_raw)

        if admission_year is None:
            problems.append({**row, "issue": "URN does not match either known format"})
            continue
        if not name_key:
            problems.append({**row, "issue": "empty name"})
            continue

        if urn in seen:
            first = seen[urn]
            entry = {**row, "first_seen": f"{first['file']} p{first['page']}"}
            if first["name_key"] == name_key:
                overlaps.append(entry)
            else:
                problems.append(
                    {**entry, "issue": f"same URN, different name ({first['name']})"}
                )
            continue
        seen[urn] = {**row, "name": name_raw, "name_key": name_key}

        records.append(
            {
                "urn": urn,
                "urn_raw": urn_raw,
                "name": name_raw,
                "name_key": name_key,
                "name_tokens": len(name_key.split()),
                "admission_year": admission_year,
                "kind": kind,
                "email": row.get("email") or None,
                "claimed_by": None,
                "claimed_at": None,
                "source_file": row["file"],
                "imported_at": now,
                **({"import_note": note} if note else {}),
            }
        )

    return records, problems, overlaps


def commit(records):
    """Upsert by URN. Re-running an import must never wipe an existing claim."""
    import db
    from pymongo import ASCENDING, UpdateOne

    db.roster.create_index([("urn", ASCENDING)], unique=True)
    db.roster.create_index([("name_key", ASCENDING)])

    # Partial, not sparse. Every unclaimed row carries claimed_by: null, and a sparse
    # index only skips rows where the field is absent — so a sparse unique index would
    # see hundreds of duplicate nulls and reject the whole import. Indexing only the
    # rows where claimed_by is a string gives the "one account per URN" guarantee
    # without the nulls colliding.
    existing = db.roster.index_information()
    if "claimed_by_1" in existing and not existing["claimed_by_1"].get(
        "partialFilterExpression"
    ):
        db.roster.drop_index("claimed_by_1")
    db.roster.create_index(
        [("claimed_by", ASCENDING)],
        unique=True,
        partialFilterExpression={"claimed_by": {"$type": "string"}},
    )

    ops = [
        UpdateOne(
            {"urn": r["urn"]},
            {
                # claimed_by/claimed_at are deliberately absent here: they belong to
                # the verification flow, not to the roster sheet.
                "$set": {k: v for k, v in r.items() if not k.startswith("claimed")},
                "$setOnInsert": {"claimed_by": None, "claimed_at": None},
            },
            upsert=True,
        )
        for r in records
    ]
    result = db.roster.bulk_write(ops, ordered=False)
    return result.upserted_count, result.modified_count


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdfs", nargs="+", help="roster PDF(s) making up one cohort")
    ap.add_argument("--kind", default="student", help="roster kind (default: student)")
    ap.add_argument("--json", metavar="PATH", help="also write extracted rows to JSON")
    ap.add_argument("--commit", action="store_true", help="write to MongoDB")
    args = ap.parse_args()

    rows = []
    for name in args.pdfs:
        path = Path(name)
        found = parse_pdf(path)
        print(f"{path.name}: {len(found)} rows")
        rows.extend(found)

    records, problems, overlaps = build_records(rows, args.kind)

    by_year = {}
    for r in records:
        by_year[r["admission_year"]] = by_year.get(r["admission_year"], 0) + 1

    print(f"\n{len(rows)} rows read → {len(records)} unique students")
    for year in sorted(by_year):
        print(f"  admission {year}: {by_year[year]}")
    if overlaps:
        print(f"  ({len(overlaps)} repeat listings across files, imported once)")

    noted = [r for r in records if r.get("import_note")]
    if noted:
        print(f"\n{len(noted)} row(s) imported with a caveat:")
        for r in noted:
            print(f"  {r['urn_raw']:<18} {r['name']:<32} {r['import_note']}")

    single = [r for r in records if r["name_tokens"] == 1]
    if single:
        print(f"\n{len(single)} single-word names (weak match signal, will need review):")
        for r in single:
            print(f"  {r['urn_raw']:<20} {r['name']}")

    if problems:
        print(f"\n{len(problems)} row(s) needing attention:")
        for p in problems:
            print(f"  {p['file']} p{p['page']} {p['urn_raw']:<18} "
                  f"{p['name_raw']:<30} {p['issue']}")

    if args.json:
        out = [{k: v for k, v in r.items() if k != "imported_at"} for r in records]
        Path(args.json).write_text(json.dumps(out, indent=2, ensure_ascii=False))
        print(f"\nwrote {args.json}")

    if args.commit:
        inserted, updated = commit(records)
        print(f"\nmongo: {inserted} inserted, {updated} updated")
    else:
        print("\ndry run — pass --commit to write to MongoDB")


if __name__ == "__main__":
    main()
