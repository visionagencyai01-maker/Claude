#!/usr/bin/env python3
"""
Pull kitchen/bathroom company leads from Google via the official Places API
(Text Search + Place Details). This is the legitimate way to get "Google
Maps" style data - name, phone number, address, rating, review count, and
a handful of review snippets - without scraping maps.google.com directly,
which violates Google's Terms of Service and is actively defended against
(CAPTCHAs, IP blocks, and Google has taken legal action against scraping
services in the past).

Setup:
    1. Create a Google Cloud project: https://console.cloud.google.com/
    2. Enable the "Places API (New)" for that project.
    3. Create an API key, restrict it to the Places API.
    4. Google gives a recurring free monthly credit; beyond that this is a
       paid API - check current pricing at
       https://developers.google.com/maps/documentation/places/web-service/usage-and-billing
    5. export GOOGLE_PLACES_API_KEY=your_key_here

Usage:
    python google_places_search.py --query "kitchen fitters in Manchester" --out output/google_leads.csv
    python google_places_search.py --towns-file uk_towns.txt --trade "bathroom fitters" --out output/google_leads.csv
    python google_places_search.py --towns-file uk_towns.txt --trades-file trades.txt --out output/google_leads.csv

Notes:
    - Text Search returns up to 20 results per query (no scrolling infinite
      results the way the Maps website does), so for real coverage you loop
      over towns/postcodes/trades as separate queries (see --towns-file and
      --trades-file, which combine as every town x every trade phrase).
    - --trades-file makes many more API calls (towns x trades) - mind the
      Places API billing (see setup notes above) before running it against
      the full uk_towns.txt list.
    - Respect people's opt-outs: screen numbers against the Corporate TPS
      (https://www.ctps.info) before cold-calling. See README.md.
"""
import argparse
import csv
import os
import sys
import time

import requests

TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

SEARCH_FIELD_MASK = "places.id,places.displayName,places.formattedAddress"
DETAILS_FIELD_MASK = (
    "id,displayName,formattedAddress,internationalPhoneNumber,"
    "websiteUri,rating,userRatingCount,reviews"
)


def text_search(query: str, api_key: str) -> list[dict]:
    resp = requests.post(
        TEXT_SEARCH_URL,
        json={"textQuery": query, "regionCode": "GB"},
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": SEARCH_FIELD_MASK,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("places", [])


def place_details(place_id: str, api_key: str) -> dict:
    resp = requests.get(
        DETAILS_URL.format(place_id=place_id),
        headers={
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": DETAILS_FIELD_MASK,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def run_query(query: str, api_key: str, delay: float) -> list[dict]:
    rows = []
    for place in text_search(query, api_key):
        place_id = place.get("id")
        if not place_id:
            continue
        details = place_details(place_id, api_key)
        time.sleep(delay)

        reviews = details.get("reviews", []) or []
        review_snippets = " | ".join(
            (r.get("text", {}) or {}).get("text", "")[:200] for r in reviews[:3]
        )

        rows.append({
            "company_name": (details.get("displayName", {}) or {}).get("text", ""),
            "phone": details.get("internationalPhoneNumber", ""),
            "address": details.get("formattedAddress", ""),
            "website": details.get("websiteUri", ""),
            "rating": details.get("rating", ""),
            "review_count": details.get("userRatingCount", ""),
            "sample_reviews": review_snippets,
            "source_query": query,
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--query", help='Single search query, e.g. "bathroom fitters in Leeds"')
    ap.add_argument(
        "--towns-file",
        help="Text file, one UK town/postcode area per line, combined with --trade or --trades-file",
    )
    ap.add_argument("--trade", default="kitchen and bathroom fitters", help="Single trade phrase used with --towns-file")
    ap.add_argument(
        "--trades-file",
        help="Text file, one trade phrase per line (e.g. trades.txt) - combined with --towns-file as every town x every trade",
    )
    ap.add_argument("--out", default="output/google_leads.csv")
    ap.add_argument("--delay", type=float, default=0.2)
    args = ap.parse_args()

    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        print("Set GOOGLE_PLACES_API_KEY - see script docstring for setup.", file=sys.stderr)
        sys.exit(1)

    queries = []
    if args.query:
        queries.append(args.query)
    if args.towns_file:
        with open(args.towns_file, encoding="utf-8") as f:
            towns = [line.strip() for line in f if line.strip()]

        if args.trades_file:
            with open(args.trades_file, encoding="utf-8") as f:
                trades = [line.strip() for line in f if line.strip()]
        else:
            trades = [args.trade]

        for town in towns:
            for trade in trades:
                queries.append(f"{trade} in {town}")
    if not queries:
        print("Provide --query or --towns-file", file=sys.stderr)
        sys.exit(1)

    all_rows = []
    seen = set()
    for q in queries:
        print(f"Searching: {q}", file=sys.stderr)
        try:
            for row in run_query(q, api_key, args.delay):
                key = (row["company_name"], row["phone"])
                if key not in seen:
                    seen.add(key)
                    all_rows.append(row)
        except requests.RequestException as exc:
            print(f"  failed: {exc}", file=sys.stderr)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "company_name", "phone", "address", "website",
                "rating", "review_count", "sample_reviews", "source_query",
            ],
        )
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Wrote {len(all_rows)} leads to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
