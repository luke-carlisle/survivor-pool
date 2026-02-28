"""
Fundas Friends Survivor 50 — Auto Scraper v2
Tries multiple sources in order:
  1. Wikipedia API (most reliable, fully open)
  2. Survivor Fandom wiki (with proper browser headers)
Falls back to existing data if all sources fail.
"""

import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), "survivor_data.json")

NAME_MAP = {
    "Aubry Bracco":"Aubrey","Aubry":"Aubrey","Aubrey":"Aubrey",
    "Genevieve Mushaluk":"Genevieve","Genevieve":"Genevieve",
    "Rizo Velovic":"Rizo","Rizo":"Rizo",
    "Rick Devens":"Devens","Rick":"Devens","Devens":"Devens",
    "Stephenie LaGrossa":"Steph","Stephenie":"Steph","Steph":"Steph",
    "Cirie Fields":"Cirie","Cirie":"Cirie",
    "Charlie Davis":"Charlie","Charlie":"Charlie",
    "Kamilla Karthigesu":"Kamilla","Kamilla":"Kamilla",
    "Tiffany Ervin":"Tiffany","Tiffany":"Tiffany",
    "Colby Donaldson":"Colby","Colby":"Colby",
    "Emily Flippen":"Emily","Emily":"Emily",
    "Joe Hunter":"Joe","Joe":"Joe",
    "Jenna Lewis-Dougherty":"Jenna","Jenna Lewis":"Jenna","Jenna":"Jenna",
    "Benjamin Wade":"Coach","Coach Wade":"Coach","Coach":"Coach",
    "Christian Hubicki":"Christian","Christian":"Christian",
    "Mike White":"Mike","Mike":"Mike",
    "Dee Valladares":"Dee","Dee":"Dee",
    "Savannah Louie":"Savanah","Savanah":"Savanah",
    "Jonathan Young":"Josh","Jonathan":"Josh","Josh":"Josh",
    "Chrissy Hofbeck":"Chrissy","Chrissy":"Chrissy",
    "Ozzy Lusth":"Ozzy","Ozzy":"Ozzy",
    "Kyle Fraser":"Kyle","Kyle":"Kyle",
    "Angelina Keeley":"Angelina","Angelina":"Angelina",
    "Q Burdette":"Q","Q":"Q",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "Connection": "keep-alive",
}

def fetch(url, extra_headers=None):
    h = dict(HEADERS)
    if extra_headers:
        h.update(extra_headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def normalize(name):
    name = name.strip()
    if name in NAME_MAP:
        return NAME_MAP[name]
    first = name.split()[0] if name else ""
    return NAME_MAP.get(first)

def strip_tags(html):
    return re.sub(r"<[^>]+>", "", html)

def load_existing():
    try:
        with open(DATA_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"episode":0,"eliminated":[],"milestones":{},"scrape_status":"no_data"}

def save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved: episode={data['episode']}, eliminated={data['eliminated']}, status={data['scrape_status']}")

def parse_wikitext(text, source=""):
    eliminated = set()
    milestones = {}
    episode_count = 0

    ep_nums = re.findall(r'[Ee]pisode[s]?\s*(\d+)', text)
    if ep_nums:
        episode_count = max((int(n) for n in ep_nums if int(n) <= 30), default=0)

    rows = re.split(r'\|-', text)
    for row in rows:
        is_elim = bool(re.search(r'[Vv]oted\s+[Oo]ut|[Ee]liminated|[Qq]uit|[Mm]edevac|[Ff]ire[- ][Mm]aking', row))
        if not is_elim:
            continue
        names_found = re.findall(r'\[\[([^\]|]+)', row)
        names_found += re.findall(r'\|\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s*\|', row)
        for name in names_found:
            key = normalize(name.strip())
            if key:
                eliminated.add(key)

    merge_section = re.search(r'[Mm]erge[^.]{0,500}', text)
    if merge_section:
        merge_keys = [normalize(n) for n in re.findall(r'\[\[([^\]|]+)', merge_section.group(0)) if normalize(n)]
        if merge_keys:
            milestones["merge"] = list(set(merge_keys))

    jury_section = re.search(r'[Jj]ury[^.]{0,500}', text)
    if jury_section:
        jury_keys = [normalize(n) for n in re.findall(r'\[\[([^\]|]+)', jury_section.group(0)) if normalize(n)]
        if jury_keys:
            milestones["jury"] = list(set(jury_keys))

    winner_match = re.search(r'[Ss]ole\s+[Ss]urvivor[^\n]{0,100}\[\[([^\]|]+)', text)
    if winner_match:
        wk = normalize(winner_match.group(1))
        if wk:
            milestones["winner"] = wk

    result = {
        "episode": episode_count,
        "eliminated": list(eliminated),
        "milestones": milestones,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "scrape_status": "ok_wikipedia"
    }
    print(f"    Parsed: {result}")
    return result

def scrape_wikipedia():
    print("  Trying Wikipedia API...")
    titles = [
        "Survivor 50",
        "Survivor: In the Hands of the Fans",
        "Survivor (season 50)",
    ]
    # Also try a search first
    try:
        search_url = (
            "https://en.wikipedia.org/w/api.php?action=query&list=search"
            "&srsearch=Survivor+season+50+CBS+2026&format=json&srlimit=3"
        )
        raw = fetch(search_url, {"Accept":"application/json"})
        found = [r["title"] for r in json.loads(raw).get("query",{}).get("search",[])]
        print(f"    Search found: {found}")
        titles = found + titles
    except Exception as e:
        print(f"    Search failed: {e}")

    for title in titles:
        try:
            encoded = urllib.parse.quote(title)
            url = (f"https://en.wikipedia.org/w/api.php?action=parse&page={encoded}"
                   f"&prop=wikitext&format=json")
            raw = fetch(url, {"Accept":"application/json"})
            data = json.loads(raw)
            if "error" in data:
                print(f"    '{title}': {data['error'].get('info','error')}")
                continue
            wikitext = data.get("parse",{}).get("wikitext",{}).get("*","")
            if wikitext:
                print(f"    Got wikitext for '{title}' ({len(wikitext)} chars)")
                return parse_wikitext(wikitext, title)
        except Exception as e:
            print(f"    '{title}' failed: {e}")
    return None

def scrape_fandom():
    print("  Trying Fandom wiki with browser headers...")
    urls = [
        "https://survivor.fandom.com/wiki/Survivor_50",
        "https://survivor.fandom.com/wiki/Survivor:_In_the_Hands_of_the_Fans",
    ]
    for url in urls:
        try:
            html = fetch(url)
            print(f"    Got {len(html)} bytes")
            # Parse HTML elimination tables
            eliminated = set()
            text = strip_tags(html)
            ep_nums = re.findall(r'[Ee]pisode\s+(\d+)', text)
            episode_count = max((int(n) for n in ep_nums if int(n) <= 30), default=0)
            for line in text.split('\n'):
                if re.search(r'[Vv]oted\s+[Oo]ut|[Ee]liminated|[Qq]uit|[Mm]edevac', line):
                    for name, key in NAME_MAP.items():
                        if name.lower() in line.lower():
                            eliminated.add(key)
            return {
                "episode": episode_count,
                "eliminated": list(eliminated),
                "milestones": {},
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "scrape_status": "ok_fandom"
            }
        except Exception as e:
            print(f"    {url} failed: {e}")
    return None

# ── MANUAL OVERRIDE ───────────────────────────────────────────────────────────
# Set USE_MANUAL_OVERRIDE = True and fill in MANUAL_DATA if scraping fails.
# Then go to Render -> Cron Job -> "Trigger Run"

USE_MANUAL_OVERRIDE = False

MANUAL_DATA = {
    "episode": 0,
    "eliminated": [],
    # Examples:
    # "eliminated": ["Jenna", "Coach"],
    "milestones": {
        # "merge":  ["Aubrey","Cirie","Joe","Devens","Mike","Dee","Steph","Colby","Emily","Charlie","Kamilla","Tiffany","Angelina"],
        # "jury":   ["Coach","Jenna"],
        # "final3": ["Aubrey","Cirie","Mike"],
        # "winner": "Aubrey"
    },
    "last_updated": datetime.now(timezone.utc).isoformat(),
    "scrape_status": "manual"
}

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n[{datetime.now(timezone.utc).isoformat()}] Survivor 50 scraper starting...")
    existing = load_existing()
    print(f"  Existing: episode={existing.get('episode',0)}, eliminated={existing.get('eliminated',[])}")

    if USE_MANUAL_OVERRIDE:
        print("  Using manual override")
        save(MANUAL_DATA)
        return MANUAL_DATA

    result = scrape_wikipedia()
    if result and (result["episode"] > 0 or result["eliminated"]):
        print("  Wikipedia succeeded")
        save(result)
        return result
    print("  Wikipedia returned no useful data (article may not exist yet)")

    result = scrape_fandom()
    if result and (result["episode"] > 0 or result["eliminated"]):
        print("  Fandom succeeded")
        save(result)
        return result
    print("  Fandom returned no useful data")

    print("  All sources failed. Keeping existing data.")
    existing["scrape_status"] = "all_failed_kept_existing"
    existing["last_updated"] = datetime.now(timezone.utc).isoformat()
    save(existing)
    return existing

if __name__ == "__main__":
    main()
