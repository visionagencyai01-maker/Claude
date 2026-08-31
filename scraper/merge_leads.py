#!/usr/bin/env python3
"""
Merge and de-duplicate the CSVs produced by scrape_kbsa.py,
companies_house_search.py, and google_places_search.py into one master
lead list.

Dedup key: normalized UK phone number when present, otherwise normalized
company name. Rows sharing a key are merged - non-empty fields win, and
the `sources` column records which file(s) contributed to each merged row,
so leads confirmed by more than one source are easy to spot and trust more.

Usage:
    python merge_leads.py output/*.csv --out output/master_leads.csv
    python merge_leads.py output/*.csv --out output/master_leads.csv --phone-only
"""
import argparse
import csv
import glob
import re
import sys
from collections import OrderedDict

PHONE_DIGITS_RE = re.compile(r"\D+")
COMPANY_SUFFIX_RE = re.compile(r"\b(ltd|limited|llp|plc|company|co)\b\.?", re.IGNORECASE)

MERGE_FIELDS = [
    "company_name", "phone", "address", "website",
    "rating", "review_count", "company_number", "sic_codes",
]


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = PHONE_DIGITS_RE.sub("", phone)
    if digits.startswith("44"):
        digits = "0" + digits[2:]
    elif digits.startswith("0044"):
        digits = "0" + digits[4:]
    return digits


def normalize_name(name: str) -> str:
    if not name:
        return ""
    name = COMPANY_SUFFIX_RE.sub("", name)
    name = re.sub(r"[^a-z0-9]+", " ", name.lower())
    return name.strip()


def load_rows(paths):
    for path in paths:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["_source_file"] = path
                yield row


def merge(rows):
    merged = OrderedDict()

    for row in rows:
        company = row.get("company_name") or ""
        phone_norm = normalize_phone(row.get("phone", ""))
        key = phone_norm or normalize_name(company)
        if not key:
            continue

        source = row["_source_file"]
        if key not in merged:
            entry = {field: row.get(field, "") for field in MERGE_FIELDS}
            entry["sources"] = {source}
            merged[key] = entry
        else:
            entry = merged[key]
            entry["sources"].add(source)
            for field in MERGE_FIELDS:
                if not entry.get(field) and row.get(field):
                    entry[field] = row[field]

    return merged


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+", help="Input CSV files (shell globs like output/*.csv are fine)")
    ap.add_argument("--out", default="output/master_leads.csv")
    ap.add_argument(
        "--phone-only",
        action="store_true",
        help="Drop leads with no phone number - useful since this list is for cold calling",
    )
    args = ap.parse_args()

    paths = []
    for pattern in args.inputs:
        matched = glob.glob(pattern)
        paths.extend(matched if matched else [pattern])
    paths = [p for p in paths if p]

    if not paths:
        print("No input files matched.", file=sys.stderr)
        sys.exit(1)

    merged = merge(load_rows(paths))

    rows_out = list(merged.values())
    if args.phone_only:
        rows_out = [r for r in rows_out if r["phone"]]
    rows_out.sort(key=lambda r: r["company_name"].lower())

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MERGE_FIELDS + ["sources"])
        writer.writeheader()
        for row in rows_out:
            out_row = dict(row)
            out_row["sources"] = ";".join(sorted(row["sources"]))
            writer.writerow(out_row)

    print(
        f"Merged {len(paths)} file(s) -> {len(rows_out)} unique leads "
        f"({'phone-only' if args.phone_only else 'all'}) written to {args.out}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
