#!/usr/bin/env python3
"""
Scrape the KBSA (Kitchen Bathroom Bedroom Specialists Association) member
directory at kbsa.org.uk/members for UK kitchen/bathroom retailer leads.

KBSA members are independent kitchen/bathroom showrooms who list themselves
publicly so consumers and trade contacts can find them - this is the
lowest-risk directory to work with, but you should still:
  - Check https://www.kbsa.org.uk/robots.txt yourself before running this
    at any real volume, and re-check it periodically (sites change it).
  - Keep the rate limit conservative (default: 1 request every 2 seconds).
  - Screen any number you intend to cold-call against the Corporate
    Telephone Preference Service (https://www.ctps.info) before calling -
    this is a legal requirement under UK PECR, not optional. See README.md.

Usage:
    pip install -r requirements.txt
    python scrape_kbsa.py --out output/kbsa_leads.csv
"""
import argparse
import csv
import re
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.kbsa.org.uk"
LISTING_URL = f"{BASE_URL}/members"
HEADERS = {
    "User-Agent": "LeadListBot/1.0 (+contact: replace-with-your-email@example.com)"
}
PHONE_RE = re.compile(r"(?:\+44\s?|0)(?:\d[\s-]?){9,10}\d")


def fetch(url: str, delay: float) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    time.sleep(delay)
    return BeautifulSoup(resp.text, "lxml")


def collect_member_links(delay: float) -> list[str]:
    """Walk the /members listing (and any pagination) for profile URLs."""
    links: set[str] = set()
    seen_pages: set[str] = set()
    to_visit = [LISTING_URL]

    while to_visit:
        page_url = to_visit.pop()
        if page_url in seen_pages:
            continue
        seen_pages.add(page_url)

        soup = fetch(page_url, delay)

        for a in soup.select('a[href*="/members/"]'):
            href = a.get("href", "")
            full = urljoin(BASE_URL, href)
            # Skip the listing page itself and non-member links (e.g. /members/kbsa)
            if full.rstrip("/") == LISTING_URL:
                continue
            if "/members/" in full:
                links.add(full.split("?")[0])

        # Follow simple pagination links if present (?page=2, /members/page/2 etc.)
        for a in soup.select("a"):
            href = a.get("href", "")
            text = (a.get_text() or "").strip().lower()
            if href and ("page=" in href or "/page/" in href) and text in {
                "next",
                ">",
                "next page",
            }:
                nxt = urljoin(BASE_URL, href)
                if nxt not in seen_pages:
                    to_visit.append(nxt)

    return sorted(links)


def parse_member_page(url: str, delay: float) -> dict:
    soup = fetch(url, delay)
    text = soup.get_text(" ", strip=True)

    name_el = soup.find("h1")
    name = name_el.get_text(strip=True) if name_el else url.rstrip("/").rsplit("/", 1)[-1]

    phone = ""
    tel_link = soup.select_one('a[href^="tel:"]')
    if tel_link:
        phone = tel_link.get("href", "").replace("tel:", "").strip()
    else:
        match = PHONE_RE.search(text)
        if match:
            phone = match.group(0)

    website = ""
    for a in soup.select("a[href]"):
        href = a["href"]
        if href.startswith("http") and "kbsa.org.uk" not in href:
            website = href
            break

    address = ""
    addr_el = soup.find(attrs={"class": re.compile("address", re.I)})
    if addr_el:
        address = addr_el.get_text(" ", strip=True)

    return {
        "company_name": name,
        "phone": phone,
        "website": website,
        "address": address,
        "profile_url": url,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="output/kbsa_leads.csv", help="CSV output path")
    ap.add_argument(
        "--delay", type=float, default=2.0, help="Seconds to wait between requests"
    )
    ap.add_argument(
        "--limit", type=int, default=0, help="Stop after N members (0 = no limit)"
    )
    args = ap.parse_args()

    print(f"Fetching member listing from {LISTING_URL} ...", file=sys.stderr)
    member_links = collect_member_links(args.delay)
    if args.limit:
        member_links = member_links[: args.limit]
    print(f"Found {len(member_links)} member profile links.", file=sys.stderr)

    rows = []
    for i, link in enumerate(member_links, 1):
        print(f"[{i}/{len(member_links)}] {link}", file=sys.stderr)
        try:
            rows.append(parse_member_page(link, args.delay))
        except requests.RequestException as exc:
            print(f"  failed: {exc}", file=sys.stderr)

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["company_name", "phone", "website", "address", "profile_url"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} leads to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
