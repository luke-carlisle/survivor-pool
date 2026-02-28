"""
Fundas Friends Survivor 50 — Scraper v3
Uses the official Fandom MediaWiki API — the right way to read fan wiki data.
No scraping, no bot detection, no 403s.

API docs: https://survivor.fandom.com/api.php
"""

import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), "survivor_data.json")

# ── NAME NORMALIZATION ────────────────────────────────────────────────────────
# Maps any name variant the wiki might use → our internal cast key

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

def normalize(name):
    name = name.strip()
    if name in NAME_MAP:
        return NAME_MAP[name]
    first = name.split()[0] if name else ""
    return NAME_MAP.get(first)

# ── FILE I/O ──────────────────────────────────────────────────────────────────

def load_existing():
    try:
        with open(DATA_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"episode":0,"eliminated":[],"milestones":{},"scrape_status":"no_data"}

def save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved: episode={data['episode']}, "
          f"eliminated={data['eliminated']}, "
          f"status={data['scrape_status']}")

# ── FANDOM OFFICIAL API ───────────────────────────────────────────────────────
# Uses api.php (MediaWiki API) — not HTML scraping.
# Fandom explicitly supports this for fan/developer use.
# Docs: https://www.mediawiki.org/wiki/API:Main_page

FANDOM_API = "https://survivor.fandom.com/api.php"

def fandom_api_fetch(page_title):
    """Fetch wikitext for a page via the official Fandom MediaWiki API."""
    params = urllib.parse.urlencode({
        "action": "parse",
        "page": page_title,
        "prop": "wikitext",
        "format": "json",
        "formatversion": "2",
    })
    url = f"{FANDOM_API}?{params}"
    print(f"    API call: {url}")

    req = urllib.request.Request(url, headers={
        # Identify ourselves — good practice with any API
        "User-Agent": "FundasFriendsSurvivorPool/1.0 (private fan pool; not commercial)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

def find_season_page():
    """Try several likely page titles until we find one that exists."""
    candidates = [
        "Survivor 50: In the Hands of the Fans",
        "Survivor_50:_In_the_Hands_of_the_Fans",
        "Survivor 50",
        "Survivor: In the Hands of the Fans",
    ]
    for title in candidates:
        try:
            data = fandom_api_fetch(title)
            if "error" in data:
                print(f"    '{title}': page not found")
                continue
            wikitext = data.get("parse", {}).get("wikitext", "")
            if wikitext:
                print(f"    Found page: '{title}' ({len(wikitext)} chars)")
                return title, wikitext
        except Exception as e:
            print(f"    '{title}' error: {e}")
    return None, None

# ── EPISODE PAGES ─────────────────────────────────────────────────────────────
# Individual episode pages have the most reliable elimination data.
# e.g. "Episode 1 (Survivor 50)"

def fetch_episode_pages(season_title, max_ep=30):
    """Fetch individual episode pages to get per-episode boot data."""
    eliminations_by_ep = {}
    milestones = {}

    for ep_num in range(1, max_ep + 1):
        # Try common episode page title formats
        page_candidates = [
            f"Episode {ep_num} (Survivor 50)",
            f"Episode {ep_num} (Survivor: In the Hands of the Fans)",
        ]
        for title in page_candidates:
            try:
                data = fandom_api_fetch(title)
                if "error" in data:
                    continue
                wikitext = data.get("parse", {}).get("wikitext", "")
                if not wikitext:
                    continue

                print(f"    Episode {ep_num} page found ({len(wikitext)} chars)")
                booted = parse_episode_boot(wikitext, ep_num)
                if booted:
                    eliminations_by_ep[ep_num] = booted

                # Check for milestone markers
                if re.search(r'[Mm]erge|[Ss]witch.*tribe|[Tt]ribe.*[Mm]erge', wikitext):
                    if "merge" not in milestones:
                        milestones["merge_episode"] = ep_num

                break  # found a valid page, stop trying candidates

            except Exception as e:
                # Page doesn't exist = this episode hasn't aired yet, stop looking
                if "404" in str(e) or "missing" in str(e).lower():
                    print(f"    Episode {ep_num} not found — stopping at ep {ep_num-1}")
                    return ep_num - 1, eliminations_by_ep, milestones
                print(f"    Episode {ep_num} error: {e}")
                break

    return max_ep, eliminations_by_ep, milestones

def parse_episode_boot(wikitext, ep_num):
    """Extract who was voted out from an episode's wikitext."""
    booted = []

    # Pattern 1: "Voted out" followed by name in wiki link
    for match in re.finditer(
        r'[Vv]oted\s+[Oo]ut[^\n]{0,200}',
        wikitext
    ):
        names = re.findall(r'\[\[([^\]|#]+)', match.group(0))
        for name in names:
            key = normalize(name)
            if key and key not in booted:
                booted.append(key)

    # Pattern 2: Table row with elimination keyword
    for row in re.split(r'\|-', wikitext):
        if not re.search(r'[Vv]oted|[Ee]limin|[Qq]uit|[Mm]edevac', row):
            continue
        names = re.findall(r'\[\[([^\]|#]+)', row)
        for name in names:
            key = normalize(name)
            if key and key not in booted:
                booted.append(key)

    return booted

# ── PARSE SEASON PAGE ─────────────────────────────────────────────────────────

def parse_season_page(wikitext):
    """
    Parse the main season page wikitext.
    This is less precise than episode pages but gives a good overview.
    """
    eliminated = set()
    milestones = {}
    episode_count = 0

    # Episode count
    ep_nums = re.findall(r'[Ee]pisode[s]?\s*(\d+)', wikitext)
    if ep_nums:
        episode_count = max((int(n) for n in ep_nums if int(n) <= 30), default=0)

    # Voted out patterns in wikitext tables
    for row in re.split(r'\|-', wikitext):
        if not re.search(r'[Vv]oted\s+[Oo]ut|[Ee]liminated|[Qq]uit|[Mm]edevac|[Ff]ire', row):
            continue
        for name in re.findall(r'\[\[([^\]|#]+)', row):
            key = normalize(name)
            if key:
                eliminated.add(key)

    # Merge
    merge_match = re.search(r'[Mm]erge[^\n]{0,300}', wikitext)
    if merge_match:
        merge_keys = [normalize(n) for n in re.findall(r'\[\[([^\]|#]+)', merge_match.group(0)) if normalize(n)]
        if merge_keys:
            milestones["merge"] = list(set(merge_keys))

    # Jury
    jury_match = re.search(r'[Jj]ury[^\n]{0,300}', wikitext)
    if jury_match:
        jury_keys = [normalize(n) for n in re.findall(r'\[\[([^\]|#]+)', jury_match.group(0)) if normalize(n)]
        if jury_keys:
            milestones["jury"] = list(set(jury_keys))

    # Winner
    winner_match = re.search(r'[Ss]ole\s+[Ss]urvivor[^\n]{0,100}\[\[([^\]|#]+)', wikitext)
    if winner_match:
        wk = normalize(winner_match.group(1))
        if wk:
            milestones["winner"] = wk

    return episode_count, list(eliminated), milestones

# ── MAIN SCRAPE ───────────────────────────────────────────────────────────────

def scrape():
    print("  Using Fandom MediaWiki API...")

    # Step 1: Find the season page
    title, wikitext = find_season_page()
    if not wikitext:
        print("  Could not find season page on Fandom wiki")
        return None

    # Step 2: Parse season page for overview
    episode_count, eliminated, milestones = parse_season_page(wikitext)
    print(f"  Season page: ep={episode_count}, eliminated={eliminated}")

    # Step 3: Validate — if numbers seem off, trust only episode count from
    # wiki structure, not content (wiki may have pre-season info)
    # Cross-check: eliminated players should be <= episode_count
    if len(eliminated) > episode_count and episode_count > 0:
        print(f"  Warning: {len(eliminated)} eliminated but only {episode_count} episodes — "
              f"wiki may have pre-season data, keeping episode count only")
        # Only keep eliminated if it seems reasonable (1-2 boots per episode max)
        if len(eliminated) > episode_count * 2:
            eliminated = []  # too many, probably wrong

    return {
        "episode": episode_count,
        "eliminated": eliminated,
        "milestones": milestones,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "scrape_status": "ok_fandom_api"
    }

# ── MANUAL OVERRIDE ───────────────────────────────────────────────────────────
# If scraping returns bad data, set USE_MANUAL_OVERRIDE = True,
# fill in MANUAL_DATA below, commit to GitHub, then Render -> Trigger Run.

USE_MANUAL_OVERRIDE = False

MANUAL_DATA = {
    "episode": 1,
    "eliminated": [],
    # "eliminated": ["Jenna"],
    "milestones": {
        # "merge":  ["Aubrey","Cirie","Joe","Devens","Mike","Dee","Steph","Colby","Charlie","Kamilla","Tiffany","Angelina","Kyle"],
        # "jury":   ["Jenna","Coach"],
        # "final3": ["Aubrey","Cirie","Mike"],
        # "winner": "Aubrey"
    },
    "last_updated": datetime.now(timezone.utc).isoformat(),
    "scrape_status": "manual"
}

# ── ENTRY POINT ───────────────────────────────────────────────────────────────

def main():
    print(f"\n[{datetime.now(timezone.utc).isoformat()}] Survivor 50 scraper starting...")
    existing = load_existing()
    print(f"  Existing: episode={existing.get('episode',0)}, "
          f"eliminated={existing.get('eliminated',[])}")

    if USE_MANUAL_OVERRIDE:
        print("  Manual override enabled")
        save(MANUAL_DATA)
        return MANUAL_DATA

    result = scrape()

    if result and result["episode"] >= 0:
        save(result)
        return result

    print("  Scrape failed, keeping existing data")
    existing["scrape_status"] = "failed_kept_existing"
    existing["last_updated"] = datetime.now(timezone.utc).isoformat()
    save(existing)
    return existing

if __name__ == "__main__":
    main()
