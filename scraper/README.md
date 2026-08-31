# UK Kitchen & Bathroom Company Lead Scraper

Three scripts, three different data sources, chosen because they're each
legitimate ways to get UK kitchen/bathroom company contact data - unlike
scraping Yell, Checkatrade, or Google Maps directly, all of which explicitly
prohibit bulk data harvesting in their Terms of Service.

| Script | Source | Gives you | Legal basis |
|---|---|---|---|
| `scrape_kbsa.py` | kbsa.org.uk member directory | Company name, phone, address, website | Public directory published for exactly this purpose; be a polite, rate-limited crawler |
| `companies_house_search.py` | Companies House API | Verified company name, registered address, SIC code, incorporation date | Official free UK government API |
| `google_places_search.py` | Google Places API | Company name, phone, address, rating, review count/snippets | Official paid Google API (replaces scraping Google Maps, which is ToS-prohibited and actively blocked) |
| `merge_leads.py` | the three CSVs above | One de-duplicated master list, phone/name-matched, with a `sources` column | n/a - just merges your own output |

None of this ran inside the Claude session that generated it — this sandbox's
network policy blocks outbound requests to arbitrary websites, so these
scripts are meant to be **run by you**, locally or in an environment with
normal internet access.

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
# KBSA member directory (no API key needed)
python scrape_kbsa.py --out output/kbsa_leads.csv

# Companies House (free API key: https://developer.company-information.service.gov.uk/)
# Default --sic already covers the 8 kitchen/bathroom-relevant codes (see script docstring)
export COMPANIES_HOUSE_API_KEY=your_key
python companies_house_search.py --out output/companies_house.csv

# Google Places (paid API beyond free monthly credit: console.cloud.google.com)
export GOOGLE_PLACES_API_KEY=your_key
# trades.txt has 10 trade phrases (kitchen fitters, bathroom showroom, wet room installers, ...)
# uk_towns.txt has 30 UK towns - this combination is 300 API calls, so start smaller if testing
python google_places_search.py --towns-file uk_towns.txt --trades-file trades.txt --out output/google_leads.csv

# Merge everything into one de-duplicated master list
python merge_leads.py output/*.csv --out output/master_leads.csv --phone-only
```

`merge_leads.py` de-dupes by normalized phone number (falling back to
normalized company name when a row has no phone), merges non-empty fields
across sources, and records which file(s) each lead came from in a
`sources` column - useful to prioritize leads confirmed by more than one
source. `--phone-only` drops rows with no phone number, since this list is
for cold calling.

## Before you cold call: UK compliance basics

This isn't legal advice, but three things are non-negotiable for a UK cold
calling list:

1. **Screen against the Corporate Telephone Preference Service (CTPS)**
   before calling any business number: https://www.ctps.info. Calling a
   CTPS-registered number without consent is a breach of PECR and the ICO
   does fine over it.
2. **Identify yourself and your organisation** at the start of every call,
   and make sure your outbound number displays (no withheld numbers) —
   both are PECR requirements.
3. **Keep a do-not-call suppression list** and honour opt-out requests
   immediately, permanently.

See the ICO's direct marketing guidance for the full rules:
https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/

## Scraper etiquette (`scrape_kbsa.py`)

- Check `https://www.kbsa.org.uk/robots.txt` yourself before running this
  at volume, and re-check periodically.
- Keep `--delay` at 2 seconds or higher (the default) — this is a small
  trade body's website, not a CDN-backed platform.
- Set a real contact email in the `HEADERS` User-Agent string in the script
  so the site owner can reach you if there's an issue.
- If KBSA ever asks you to stop or changes their terms to disallow this,
  stop.
