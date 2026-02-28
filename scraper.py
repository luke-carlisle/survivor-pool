"""
Fundas Friends Survivor 50 — Auto Scraper
Reads the Survivor Fandom wiki and writes survivor_data.json
Run automatically every night via Render cron job.
"""

import json
import re
import urllib.request
from datetime import datetime, timezone

# ── CONFIGURATION ────────────────────────────────────────────────────────────

SEASON = 50
WIKI_URL = "https://survivor.fandom.com/wiki/Survivor_50"

# These are the exact cast member keys used in your HTML page.
# If the wiki spells a name differently, add a mapping here.
NAME_MAP = {
    "Aubry Bracco":              "Aubrey",
    "Aubry":                     "Aubrey",
    "Aubrey":                    "Aubrey",
    "Genevieve Mushaluk":        "Genevieve",
    "Genevieve":                 "Genevieve",
    "Rizo Velovic":              "Rizo",
    "Rizo":                      "Rizo",
    "Rick Devens":               "Devens",
    "Rick":                      "Devens",
    "Devens":                    "Devens",
    "Stephenie LaGrossa":        "Steph",
    "Stephenie":                 "Steph",
    "Steph":                     "Steph",
    "Cirie Fields":              "Cirie",
    "Cirie":                     "Cirie",
    "Charlie Davis":             "Charlie",
    "Charlie":                   "Charlie",
    "Kamilla Karthigesu":        "Kamilla",
    "Kamilla":                   "Kamilla",
    "Tiffany Ervin":             "Tiffany",
    "Tiffany":                   "Tiffany",
    "Colby Donaldson":           "Colby",
    "Colby":                     "Colby",
    "Emily Flippen":             "Emily",
    "Emily":                     "Emily",
    "Joe Hunter":                "Joe",
    "Joe":                       "Joe",
    "Jenna Lewis-Dougherty":     "Jenna",
    "Jenna Lewis":               "Jenna",
    "Jenna":                     "Jenna",
    "Benjamin Wade":             "Coach",
    "Coach Wade":                "Coach",
    "Coach":                     "Coach",
    "Christian Hubicki":         "Christian",
    "Christian":                 "Christian",
    "Mike White":                "Mike",
    "Mike":                      "Mike",
    "Dee Valladares":            "Dee",
    "Dee":                       "Dee",
    "Savannah Louie":            "Savanah",
    "Savanah":                   "Savanah",
    "Jonathan Young":            "Josh",
    "Jonathan":                  "Josh",
    "Josh":                      "Josh",
    "Chrissy Hofbeck":           "Chrissy",
    "Chrissy":                   "Chrissy",
    "Ozzy Lusth":                "Ozzy",
    "Ozzy":                      "Ozzy",
    "Kyle Fraser":               "Kyle",
    "Kyle":                      "Kyle",
    "Angelina Keeley":           "Angelina",
    "Angelina":                  "Angelina",
    "Q Burdette":                "Q",
    "Q":                         "Q",
}

ALL_CAST = [
    "Aubrey","Genevieve","Rizo","Devens","Steph","Cirie","Charlie","Kamilla",
    "Tiffany","Colby","Emily","Joe","Jenna","Coach","Christian","Mike","Dee",
    "Savanah","Josh","Chrissy","Ozzy","Kyle","Angelina","Q"
]

# ── HELPERS ──────────────────────────────────────────────────────────────────

def normalize(name):
    """Map a wiki name to our internal cast key."""
    name = name.strip()
    if name in NAME_MAP:
        return NAME_MAP[name]
    # Try first name only
    first = name.split()[0] if name else ""
    if first in NAME_MAP:
        return NAME_MAP[first]
    return None


def fetch_html(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; FundasFriendsSurvivorPool/1.0)"
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def strip_tags(html):
    """Very simple tag stripper."""
    return re.sub(r"<[^>]+>", "", html)


# ── SCRAPER ──────────────────────────────────────────────────────────────────

def scrape():
    """
    Scrape the Survivor Fandom wiki and return structured episode data.
    Falls back to the previous saved data if scraping fails.
    """
    print(f"[{datetime.now()}] Scraping {WIKI_URL} ...")

    try:
        html = fetch_html(WIKI_URL)
    except Exception as e:
        print(f"  ERROR fetching wiki: {e}")
        return None

    # ── Find episode count ────────────────────────────────────────────────
    # Look for patterns like "Episode 1", "Episode 2" etc in the HTML
    episode_numbers = re.findall(r'[Ee]pisode\s+(\d+)', html)
    max_episode = max([int(n) for n in episode_numbers], default=0)
    max_episode = min(max_episode, 26)  # cap at 26 (typical season length)
    print(f"  Detected up to episode {max_episode}")

    # ── Find eliminated players ───────────────────────────────────────────
    # The wiki elimination table uses patterns like "Voted Out", "Eliminated"
    # We look for cast names near those phrases
    eliminated = []

    # Strategy 1: Look for "Voted Out" sections with names
    voted_out_blocks = re.findall(
        r'(?:Voted\s+[Oo]ut|Eliminated|Sole\s+Survivor)[^<]{0,200}',
        html
    )

    # Strategy 2: Look for the episode summary table rows
    # Wiki tables typically have: Episode | Tribal | Voted Out
    table_rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)

    found_names = set()
    for row in table_rows:
        text = strip_tags(row)
        for cast_name, key in NAME_MAP.items():
            if cast_name.lower() in text.lower() and (
                "voted out" in text.lower() or
                "eliminated" in text.lower() or
                "quit" in text.lower() or
                "medevac" in text.lower()
            ):
                found_names.add(key)

    # Strategy 3: Check individual cast member pages for elimination info
    # Look for "Finish" or "Days lasted" patterns
    finish_pattern = re.findall(
        r'(?:finish|placement|days)["\s:>]+([^<"]{3,40})',
        html, re.IGNORECASE
    )

    eliminated = list(found_names)
    print(f"  Found {len(eliminated)} eliminated players: {eliminated}")

    # ── Find milestones ───────────────────────────────────────────────────
    milestones = {}

    # Merge detection
    merge_names = []
    merge_blocks = re.findall(
        r'(?:merge|merged)[^<]{0,500}',
        html, re.IGNORECASE
    )
    for block in merge_blocks:
        for cast_name, key in NAME_MAP.items():
            if cast_name.lower() in block.lower():
                merge_names.append(key)
    if merge_names:
        milestones["merge"] = list(set(merge_names))

    # Jury detection
    jury_names = []
    jury_blocks = re.findall(
        r'(?:jury member|joined the jury)[^<]{0,300}',
        html, re.IGNORECASE
    )
    for block in jury_blocks:
        for cast_name, key in NAME_MAP.items():
            if cast_name.lower() in block.lower():
                jury_names.append(key)
    if jury_names:
        milestones["jury"] = list(set(jury_names))

    # Winner detection
    winner_match = re.search(
        r'(?:Sole Survivor|winner)["\s:>]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)',
        html
    )
    if winner_match:
        winner_key = normalize(winner_match.group(1))
        if winner_key:
            milestones["winner"] = winner_key

    return {
        "episode": max_episode,
        "eliminated": eliminated,
        "milestones": milestones,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "scrape_status": "ok"
    }


# ── MANUAL OVERRIDE ───────────────────────────────────────────────────────────
# If the scraper gets confused, edit this function directly.
# Set USE_MANUAL_OVERRIDE = True, fill in the data, and redeploy.

USE_MANUAL_OVERRIDE = False

MANUAL_DATA = {
    "episode": 0,
    "eliminated": [],
    # Examples:
    # "eliminated": ["Jenna", "Coach"],
    "milestones": {
        # "merge":  ["Aubrey","Cirie","Joe","Devens","Mike","Dee","Steph","Colby","Emily","Joe","Charlie","Kamilla","Tiffany"],
        # "jury":   ["Coach","Jenna"],
        # "final3": ["Aubrey","Cirie","Mike"],
        # "winner": "Aubrey"
    },
    "last_updated": datetime.now(timezone.utc).isoformat(),
    "scrape_status": "manual"
}


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    # Load existing data as fallback
    existing = {
        "episode": 0,
        "eliminated": [],
        "milestones": {},
        "last_updated": None,
        "scrape_status": "no_data"
    }
    try:
        with open("survivor_data.json") as f:
            existing = json.load(f)
        print(f"  Loaded existing data (episode {existing.get('episode',0)})")
    except FileNotFoundError:
        print("  No existing data file, starting fresh")

    if USE_MANUAL_OVERRIDE:
        print("  Using manual override data")
        data = MANUAL_DATA
    else:
        data = scrape()
        if data is None:
            print("  Scrape failed, keeping existing data")
            data = existing
            data["scrape_status"] = "failed_kept_existing"

    with open("survivor_data.json", "w") as f:
        json.dump(data, f, indent=2)

    print(f"  Saved survivor_data.json (episode {data['episode']}, "
          f"{len(data['eliminated'])} eliminated, status: {data['scrape_status']})")
    return data


if __name__ == "__main__":
    main()
