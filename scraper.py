"""
Fundas Friends Survivor 50 — Scraper v4
Parses the Fandom wiki Castaways table using the official MediaWiki API.
Based on confirmed wikitext structure from Survivor 49.

Castaway table row format:
  | [[File:image]]
  | '''[[Name]]''' <small>age, location / occupation</small>
  | tribe info columns...
  | {{nowrap|FINISH TEXT}}
  | votes against

Finish text patterns:
  "Nth Voted Out\nDay X"
  "Nth Voted Out\nNth Jury Member\nDay X"
  "Evacuated\nDay X"
  "Eliminated\nNth Jury Member\nDay X"   (fire-making)
  "Runner-Up"
  "Second Runner-Up"
  "Sole Survivor"
"""

import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), "survivor_data.json")

FANDOM_API = "https://survivor.fandom.com/api.php"

# Map wiki name → our internal cast key
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

def fandom_fetch(page_title):
    """Fetch wikitext via the official Fandom MediaWiki API."""
    params = urllib.parse.urlencode({
        "action": "parse",
        "page": page_title,
        "prop": "wikitext",
        "format": "json",
        "formatversion": "2",
    })
    url = f"{FANDOM_API}?{params}"
    print(f"    Fetching: {url}")
    req = urllib.request.Request(url, headers={
        "User-Agent": "FundasFriendsSurvivorPool/1.0 (private fan pool; not commercial)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "error" in data:
        raise ValueError(f"API error: {data['error'].get('info','unknown')}")
    return data["parse"]["wikitext"]

def parse_castaways_table(wikitext):
    """
    Parse the ==Castaways== wikitable to extract elimination data.

    Each castaway row contains (based on confirmed S49 structure):
      - Name in '''[[Name]]''' format
      - Finish in {{nowrap|FINISH TEXT}} format

    Finish text patterns we care about:
      "Nth Voted Out"              → eliminated
      "Evacuated"                  → eliminated
      "Eliminated"                 → eliminated (fire-making loss)
      "Nth Jury Member"            → jury milestone
      "Runner-Up" / "Second Runner-Up" → final3 milestone
      "Sole Survivor"              → winner
    """
    # Find the Castaways section
    cast_start = wikitext.find("==Castaways==")
    if cast_start == -1:
        cast_start = wikitext.find("== Castaways ==")
    if cast_start == -1:
        print("    WARNING: Could not find ==Castaways== section")
        return None

    # End at the next == section ==
    next_section = re.search(r'\n==[^=]', wikitext[cast_start + 20:])
    if next_section:
        cast_section = wikitext[cast_start: cast_start + 20 + next_section.start()]
    else:
        cast_section = wikitext[cast_start:]

    print(f"    Castaways section: {len(cast_section)} chars")

    # Split into table rows (each row starts with |-  or | )
    # Each castaway is a block between |- markers
    rows = re.split(r'\n\|-', cast_section)

    eliminated = []
    jury = []
    final3 = []
    winner = None
    episode_count = 0
    still_alive = []  # players with no finish yet

    for row in rows:
        # ── Extract name ──────────────────────────────────────────────────
        # Pattern: '''[[Name]]''' or '''[[Name|Display]]'''
        name_match = re.search(r"'''\[\[([^\]|]+)(?:\|[^\]]*)?\]\]'''", row)
        if not name_match:
            continue
        raw_name = name_match.group(1).strip()
        key = normalize(raw_name)
        if not key:
            print(f"    Skipping unrecognized name: '{raw_name}'")
            continue

        # ── Extract finish ────────────────────────────────────────────────
        # Pattern: {{nowrap|FINISH TEXT}}
        finish_match = re.search(r'\{\{nowrap\|([^}]+)\}\}', row)
        if not finish_match:
            # No finish yet = still in the game
            still_alive.append(key)
            print(f"    {key}: still in game (no finish)")
            continue

        finish_raw = finish_match.group(1)
        # Clean up wiki markup inside finish
        finish = re.sub(r'<br\s*/?>', '\n', finish_raw)
        finish = re.sub(r'\{\{[^}]+\}\}', '', finish).strip()
        finish_lower = finish.lower()

        print(f"    {key}: '{finish.strip()}'")

        # ── Classify the finish ───────────────────────────────────────────

        is_out = bool(re.search(r'voted out|evacuated|eliminated|quit|medevac', finish_lower))
        is_jury = bool(re.search(r'jury member', finish_lower))
        is_runner_up = bool(re.search(r'runner.up|second runner', finish_lower))
        is_winner = bool(re.search(r'sole survivor', finish_lower))

        # Extract episode/day number for ordering
        day_match = re.search(r'[Dd]ay\s+(\d+)', finish)
        day = int(day_match.group(1)) if day_match else 999

        if is_winner:
            winner = key
            final3.append(key)
        elif is_runner_up:
            final3.append(key)
        elif is_out:
            eliminated.append((key, day))
            if is_jury:
                jury.append((key, day))
            # Track highest episode seen
            ep_match = re.search(r'(\d+)(?:st|nd|rd|th)\s+[Vv]oted', finish)
            if ep_match:
                ep_num = int(ep_match.group(1))
                if ep_num > episode_count:
                    episode_count = ep_num

    # Sort eliminations by day
    eliminated.sort(key=lambda x: x[1])
    jury.sort(key=lambda x: x[1])

    eliminated_keys = [k for k, _ in eliminated]
    jury_keys = [k for k, _ in jury]

    milestones = {}

    # Merge = first jury member's tribal + still alive players
    if jury_keys:
        # Everyone who made jury + final3 + winner + still_alive reached merge
        merge_players = jury_keys + final3 + still_alive
        if winner:
            merge_players = list(set(merge_players + [winner]))
        milestones["merge"] = list(set(merge_players))

    if jury_keys:
        milestones["jury"] = jury_keys

    if final3:
        milestones["final3"] = final3

    if winner:
        milestones["winner"] = winner

    print(f"    Result: episode={episode_count}, eliminated={eliminated_keys}")
    print(f"    Jury={jury_keys}, Final3={final3}, Winner={winner}")
    print(f"    Still alive: {still_alive}")

    return {
        "episode": episode_count,
        "eliminated": eliminated_keys,
        "milestones": milestones,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "scrape_status": "ok_fandom_api_v4"
    }

def scrape():
    """Fetch and parse the Season 50 castaways table."""
    print("  Using Fandom MediaWiki API (castaway table parser)...")

    page_titles = [
        "Survivor 50: In the Hands of the Fans",
        "Survivor_50:_In_the_Hands_of_the_Fans",
        "Survivor 50",
    ]

    for title in page_titles:
        try:
            wikitext = fandom_fetch(title)
            print(f"    Got wikitext for '{title}' ({len(wikitext)} chars)")
            result = parse_castaways_table(wikitext)
            if result is not None:
                return result
        except Exception as e:
            print(f"    '{title}' failed: {e}")

    return None

# ── MANUAL OVERRIDE ───────────────────────────────────────────────────────────
# Set USE_MANUAL_OVERRIDE = True if automatic scraping produces wrong results.
# Update MANUAL_DATA each week, commit to GitHub, then Render → Trigger Run.

USE_MANUAL_OVERRIDE = False

MANUAL_DATA = {
    "episode": 1,
    "eliminated": [],
    # "eliminated": ["Jenna"],              # after ep 1
    # "eliminated": ["Jenna", "Rizo"],      # after ep 2 (keep all previous!)
    "milestones": {
        # Add these as they happen:
        # "merge":  ["Aubrey","Cirie","Joe","Devens","Mike","Dee","Colby","Charlie","Kamilla","Tiffany","Angelina","Kyle","Q"],
        # "jury":   ["Jenna","Rizo"],
        # "final3": ["Aubrey","Cirie","Mike"],
        # "winner": "Aubrey"
    },
    "last_updated": datetime.now(timezone.utc).isoformat(),
    "scrape_status": "manual"
}

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n[{datetime.now(timezone.utc).isoformat()}] Survivor 50 scraper v4 starting...")
    existing = load_existing()
    print(f"  Existing: episode={existing.get('episode',0)}, "
          f"eliminated={existing.get('eliminated',[])}")

    if USE_MANUAL_OVERRIDE:
        print("  Manual override enabled")
        save(MANUAL_DATA)
        return MANUAL_DATA

    result = scrape()

    if result is not None:
        save(result)
        return result

    print("  Scrape failed, keeping existing data")
    existing["scrape_status"] = "failed_kept_existing"
    existing["last_updated"] = datetime.now(timezone.utc).isoformat()
    save(existing)
    return existing

if __name__ == "__main__":
    main()
