"""
daily_briefing — morning CLI briefing.

  python main.py                        # London, 5 stories, with quote, saves file
  python main.py --city Paris           # different city
  python main.py --stories 7           # more stories
  python main.py --no-quote --no-save  # skip quote, print only
  python main.py --help                # show all flags
"""

# ── Imports ────────────────────────────────────────────────────────────────────
# stdlib  = ships with Python, no install needed
# third-party = install with:  pip install requests
import argparse                  # reads CLI flags like --city London
import json                      # parses JSON text into Python dicts/lists
from datetime import datetime    # dates and times
from pathlib import Path         # file paths, cross-platform

import requests                  # HTTP requests (third-party)


# ── Settings ───────────────────────────────────────────────────────────────────
# UPPER_SNAKE_CASE = convention for values that never change while the program runs.
# Python has no true constants — this is just a naming agreement.

DEFAULT_CITY    = "London"
DEFAULT_STORIES = 5
MAX_STORIES     = 10

# Path(__file__)  → path of this file (main.py)
# .parent         → folder that contains it  (app/)
# / "briefings"   → sub-folder for saved reports  (app/briefings/)
BRIEFINGS_DIR = Path(__file__).parent / "briefings"

# {city} and {id} are placeholders filled in later with .format(city=..., id=...)
WEATHER_URL = "https://wttr.in/{city}?format=j1"
HN_TOP_URL  = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
QUOTE_URL   = "https://dummyjson.com/quotes/random"   # returns {"quote":"..","author":".."}


# ── Fetchers ───────────────────────────────────────────────────────────────────
# Each function does ONE job: talk to an API, return clean data (or a safe fallback).
#
# Type hints:  def f(x: str) -> dict | None
#              "x must be a str; the return is either a dict or None"
#              Not enforced at runtime — they are documentation for humans.

def fetch_weather(city: str) -> dict | None:
    """Return weather data for `city`, or None if the request fails."""

    # str.replace(" ", "+") makes "New York" → "New+York" (safe in a URL)
    url = WEATHER_URL.format(city=city.replace(" ", "+"))

    # try / except — run the risky code in `try`; if anything goes wrong,
    # jump to `except` instead of crashing the whole program.
    try:
        r = requests.get(url, timeout=10)   # wait at most 10 s
        r.raise_for_status()                # crash if server replied 4xx / 5xx

        # [0] = first item of the list (Python lists are 0-indexed)
        current = r.json()["current_condition"][0]

        # int() converts the strings the API sends ("22") to real integers (22)
        return {
            "city":        city,
            "temp_c":      int(current["temp_C"]),
            "feels_like":  int(current["FeelsLikeC"]),
            "description": current["weatherDesc"][0]["value"],
            "humidity":    int(current["humidity"]),
        }

    except (requests.RequestException, KeyError, json.JSONDecodeError) as err:
        print(f"⚠  Weather unavailable: {err}")
        return None   # caller checks for None and shows a friendly message


def fetch_stories(limit: int = DEFAULT_STORIES) -> list[dict]:
    """Return the top N Hacker News stories sorted by score. Never returns None."""

    # min() clamps the value so --stories 999 still only fetches MAX_STORIES
    limit = min(limit, MAX_STORIES)

    try:
        # Slice [:limit*3] takes the first (limit × 3) items from the ID list.
        # We fetch 3× what we need because some stories have no URL and get filtered out.
        ids = requests.get(HN_TOP_URL, timeout=10).json()[: limit * 3]
    except requests.RequestException as err:
        print(f"⚠  Hacker News unavailable: {err}")
        return []   # empty list is safe — callers can always iterate over it

    stories = []
    for story_id in ids:
        if len(stories) >= limit:
            break       # we have enough; stop fetching
        try:
            story = requests.get(HN_ITEM_URL.format(id=story_id), timeout=10).json()
            if story.get("title") and story.get("url"):   # skip stories without a link
                stories.append(story)
        except requests.RequestException:
            continue    # skip broken item, try the next one

    # List comprehension is already done above via the if-check inside the loop.
    # sorted() returns a NEW list; it doesn't modify `stories` in place.
    # lambda is an anonymous one-liner function:  lambda s: s.get("score", 0)
    # reverse=True → highest score first
    return sorted(stories, key=lambda s: s.get("score", 0), reverse=True)


def fetch_quote() -> dict | None:
    """Return {"text": "...", "author": "..."} or None on failure."""
    try:
        r = requests.get(QUOTE_URL, timeout=10)
        r.raise_for_status()
        item = r.json()                              # {"id":1, "quote":"...", "author":"..."}
        return {"text": item["quote"], "author": item["author"]}
    except (requests.RequestException, KeyError, json.JSONDecodeError) as err:
        print(f"⚠  Quote unavailable: {err}")
        return None


# ── Report ─────────────────────────────────────────────────────────────────────

def build_report(weather: dict | None, stories: list[dict], quote: dict | None) -> str:
    """Assemble all sections into a single Markdown string."""

    now = datetime.now()

    # strftime format codes:  %A = weekday  %d = day  %b = month  %Y = year  %H:%M = time
    header = now.strftime("%A, %d %b %Y · %H:%M")

    # Build the report as a list of lines, then join them at the end.
    # This is cleaner and faster than building one big string with +=.
    lines = [f"# Daily Briefing — {header}", "", "## Weather"]

    if weather:
        lines += [
            f"**{weather['city']}** — {weather['description']}",
            f"{weather['temp_c']}°C  (feels like {weather['feels_like']}°C)  ·  humidity {weather['humidity']}%",
        ]
    else:
        lines.append("_Unavailable_")

    lines += ["", "## Top Stories"]

    if stories:
        # enumerate(iterable, start=1) yields (1, item), (2, item), ...
        for i, s in enumerate(stories, start=1):
            # Markdown link syntax: [title](url)
            lines.append(f"{i}. [{s['title']}]({s['url']})  ↑{s.get('score', 0)}")
    else:
        lines.append("_Unavailable_")

    if quote:
        lines += ["", "## Quote", f"> {quote['text']}", f"> — {quote['author']}"]

    # "\n".join(list) puts a newline between every item and returns one string
    return "\n".join(lines)


# ── Saver ──────────────────────────────────────────────────────────────────────

def save_report(content: str, output_dir: Path) -> Path:
    """Write the report to output_dir/YYYY-MM-DD.md and return the file path."""
    output_dir.mkdir(parents=True, exist_ok=True)   # create folder if it doesn't exist
    filepath = output_dir / (datetime.now().strftime("%Y-%m-%d") + ".md")
    filepath.write_text(content, encoding="utf-8")   # open + write + close in one call
    return filepath


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    """Read command-line flags and return them as a Namespace object."""
    p = argparse.ArgumentParser(
        description="Morning briefing: weather + HN stories + quote.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,  # shows defaults in --help
    )
    p.add_argument("--city",     default=DEFAULT_CITY,     help="City for weather")
    p.add_argument("--stories",  default=DEFAULT_STORIES,  help="Number of stories", type=int, metavar="N")
    p.add_argument("--no-quote", action="store_true",      help="Skip the quote")
    p.add_argument("--no-save",  action="store_true",      help="Print only, do not save a file")
    p.add_argument("--output",   default=BRIEFINGS_DIR,    help="Folder for saved reports", type=Path)
    return p.parse_args()


# ── Main ───────────────────────────────────────────────────────────────────────
# main() reads like a table of contents — short on purpose.
# All the detail lives in the functions above.

def main():
    args = parse_args()

    print(f"Fetching weather for {args.city}…")
    weather = fetch_weather(args.city)

    print(f"Fetching top {args.stories} stories…")
    stories = fetch_stories(args.stories)

    # args.no_quote is True when --no-quote was passed; `not` flips it
    quote = None
    if not args.no_quote:
        print("Fetching quote…")
        quote = fetch_quote()

    report = build_report(weather, stories, quote)
    print("\n" + report)

    if not args.no_save:
        path = save_report(report, args.output)
        print(f"\nSaved → {path}")


# ── Entry point guard ──────────────────────────────────────────────────────────
# This block runs only when you execute the file directly: python main.py
# It is SKIPPED when another file does: import main
if __name__ == "__main__":
    main()
