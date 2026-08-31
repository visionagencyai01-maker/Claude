#!/usr/bin/env python3
"""
Pull UK kitchen/bathroom companies from the official Companies House API
(free, no ToS issue - this is a government open API meant for exactly this
kind of bulk company lookup), filtered by SIC code.

This gives you verified company names, registered addresses, incorporation
dates and SIC codes, which is useful to sanity-check or de-duplicate leads
scraped elsewhere. It does NOT return phone numbers - Companies House
doesn't collect them.

Setup:
    1. Register a free account and API key at
       https://developer.company-information.service.gov.uk/
    2. export COMPANIES_HOUSE_API_KEY=your_key_here

Usage:
    python companies_house_search.py --out output/companies_house.csv
    python companies_house_search.py --sic 43320,43221 --query kitchen --out output/companies_house.csv

Relevant SIC codes (default set covers all of these):
    43320 - Joinery installation (includes fitted kitchens)
    43221 - Plumbing, heat and air-conditioning installation (bathroom fitters)
    43299 - Other construction installation n.e.c.
    43390 - Other building completion and finishing
    47599 - Retail sale of other household equipment n.e.c. (kitchen/bathroom showrooms)
    46731 - Wholesale of wood, construction materials and sanitary equipment
    46499 - Wholesale of other household goods n.e.c.
    47520 - Retail sale of hardware, paints and glass in specialised stores
"""
import argparse
import csv
import os
import sys
import time

import requests

API_BASE = "https://api.company-information.service.gov.uk"

DEFAULT_SIC_CODES = [
    "43320",  # Joinery installation (fitted kitchens)
    "43221",  # Plumbing, heat and air-conditioning installation (bathroom fitters)
    "43299",  # Other construction installation n.e.c.
    "43390",  # Other building completion and finishing
    "47599",  # Retail sale of other household equipment n.e.c. (showrooms)
    "46731",  # Wholesale of wood, construction materials and sanitary equipment
    "46499",  # Wholesale of other household goods n.e.c.
    "47520",  # Retail sale of hardware, paints and glass
]


def search_companies(sic_code: str, query: str, api_key: str, max_results: int, delay: float):
    results = []
    start_index = 0
    page_size = 50

    while len(results) < max_results:
        params = {"sic_codes": sic_code, "size": page_size, "start_index": start_index}
        if query:
            params["q"] = query

        resp = requests.get(
            f"{API_BASE}/advanced-search/companies",
            params=params,
            auth=(api_key, ""),
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            break

        results.extend(items)
        start_index += page_size
        time.sleep(delay)

        if start_index >= data.get("hits", 0):
            break

    return results[:max_results]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--sic",
        default=",".join(DEFAULT_SIC_CODES),
        help="Comma-separated list of SIC codes to search (see docstring for the kitchen/bathroom-relevant ones)",
    )
    ap.add_argument(
        "--query",
        default="",
        help="Optional free-text filter combined with each SIC search (e.g. 'kitchen')",
    )
    ap.add_argument("--out", default="output/companies_house.csv")
    ap.add_argument("--max-results", type=int, default=200, help="Max results per SIC code")
    ap.add_argument("--delay", type=float, default=0.5)
    args = ap.parse_args()

    api_key = os.environ.get("COMPANIES_HOUSE_API_KEY")
    if not api_key:
        print(
            "Set COMPANIES_HOUSE_API_KEY (get one free at "
            "https://developer.company-information.service.gov.uk/)",
            file=sys.stderr,
        )
        sys.exit(1)

    sic_codes = [s.strip() for s in args.sic.split(",") if s.strip()]
    seen_numbers = set()
    all_items = []

    for sic_code in sic_codes:
        print(f"Searching SIC {sic_code} ...", file=sys.stderr)
        try:
            items = search_companies(sic_code, args.query, api_key, args.max_results, args.delay)
        except requests.RequestException as exc:
            print(f"  failed: {exc}", file=sys.stderr)
            continue

        for item in items:
            number = item.get("company_number")
            if number and number not in seen_numbers:
                seen_numbers.add(number)
                all_items.append(item)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["company_name", "company_number", "status", "address", "sic_codes", "date_of_creation"]
        )
        for item in all_items:
            addr = item.get("registered_office_address", {})
            address = ", ".join(
                str(v) for v in [
                    addr.get("address_line_1"),
                    addr.get("address_line_2"),
                    addr.get("locality"),
                    addr.get("postal_code"),
                ] if v
            )
            writer.writerow([
                item.get("company_name", ""),
                item.get("company_number", ""),
                item.get("company_status", ""),
                address,
                ";".join(item.get("sic_codes", []) or []),
                item.get("date_of_creation", ""),
            ])

    print(f"Wrote {len(all_items)} unique companies to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
