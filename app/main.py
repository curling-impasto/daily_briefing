"""
daily_briefing — a morning CLI briefing tool.

WHAT THIS SCRIPT DOES
─────────────────────
Every morning, run this script and it will:
  1. Fetch the current weather for a city
  2. Fetch the top stories from Hacker News
  3. Fetch a random inspirational quote
  4. Print everything as a Markdown report
  5. Optionally save the report to a file

HOW TO RUN IT
─────────────
  python main.py                           # defaults: Tel Aviv, 5 stories, with quote, save file
  python main.py --city London             # change the city
  python main.py --stories 7              # fetch 7 stories instead of 5
  python main.py --no-quote --no-save     # skip quote, don't write a file
  python main.py --help                   # show all options
"""

# ══════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ══════════════════════════════════════════════════════════════════════════════
#
# Python comes with a huge "standard library" of built-in modules.
# You import them with `import <name>` — no installation needed.
#
# Third-party packages (made by the community) need `pip install <name>` first.

import argparse   # stdlib: reads command-line flags like --city London
import json       # stdlib: converts JSON text ↔ Python dicts/lists
import logging    # stdlib: structured status messages (better than print)
import sys        # stdlib: access to system-level things (e.g. exit codes)
from datetime import datetime   # stdlib: work with dates and times
from pathlib import Path        # stdlib: handle file paths in a cross-platform way

import requests   # third-party: make HTTP requests (pip install requests)


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
#
# Constants are variables whose values never change while the program runs.
# Python convention: write them in UPPER_SNAKE_CASE so readers know at a glance
# they aren't meant to be modified.
#
# Python has NO true constants (unlike Java or C) — UPPER_CASE is just a
# naming agreement that tells other developers "please don't change this".

DEFAULT_CITY    = "Tel Aviv"   # city used when --city flag is not provided
DEFAULT_STORIES = 5            # number of HN stories when --stories is not provided
MAX_STORIES     = 10           # hard cap — prevents accidentally fetching hundreds

# Path(__file__) → the path of THIS file (main.py)
# .parent       → the folder that contains main.py  (i.e. app/)
# / "briefings" → the sub-folder where we save reports
#
# The / operator on Path objects joins path segments (like os.path.join but nicer).
BRIEFINGS_DIR = Path(__file__).parent / "briefings"

# API URLs — {city} and {id} are placeholders filled in later with .format()
WEATHER_URL = "https://wttr.in/{city}?format=j1"
HN_TOP_URL  = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
QUOTE_URL   = "https://zenquotes.io/api/random"


# ══════════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ══════════════════════════════════════════════════════════════════════════════
#
# WHY LOGGING INSTEAD OF PRINT?
#
#   print()   → shows output the USER asked for (the actual report)
#   logging   → shows what the PROGRAM is doing ("Fetching weather…")
#
# Logging adds a severity level (INFO / WARNING / ERROR) to every message,
# which makes it easy to filter noise in big projects.
#
# basicConfig sets global defaults once; every logger in the program inherits them.
# format="%(levelname)s  %(message)s" → produces lines like:  INFO  Fetching weather…

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

# __name__ is a special Python variable that equals the module's own name.
# When this file is run directly it equals "__main__"; when imported it equals
# "main" (the filename). Using it as the logger name helps trace where messages
# came from in larger apps.
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# FETCHERS  — functions that talk to external APIs
# ══════════════════════════════════════════════════════════════════════════════
#
# DESIGN RULE: each function does exactly ONE job and returns a value.
#
# TYPE HINTS
# ──────────
# Python lets you annotate what types a function accepts and returns:
#
#   def fetch_weather(city: str) -> dict | None:
#                     ─────────    ────────────
#                     "city must    "returns a dict,
#                     be a str"      OR None on failure"
#
# These hints are not enforced at runtime — they are documentation for humans
# (and tools like type-checkers).  `dict | None` means "either a dict or None".


def fetch_weather(city: str) -> dict | None:
    """
    Ask wttr.in for the current weather in `city`.

    Returns a plain dict with the fields we need, or None if anything goes wrong.
    Returning None (instead of crashing) lets the caller decide what to do.
    """

    # str.replace(" ", "+") turns "Tel Aviv" → "Tel+Aviv" so it is URL-safe.
    # str.format(city=...) fills the {city} placeholder in WEATHER_URL.
    url = WEATHER_URL.format(city=city.replace(" ", "+"))

    # TRY / EXCEPT — error handling
    # ───────────────────────────────
    # Code inside `try` runs normally.
    # If an exception (error) is raised, Python jumps to the matching `except` block.
    # We catch three possible failure modes:
    #   requests.RequestException → network error (no internet, timeout, bad status)
    #   KeyError                  → the JSON came back but was missing a field we expected
    #   json.JSONDecodeError      → the response body wasn't valid JSON at all
    try:
        # requests.get() sends an HTTP GET request and waits up to 10 seconds.
        # timeout=10 prevents the script from hanging forever if the server is slow.
        response = requests.get(url, timeout=10)

        # raise_for_status() raises an exception automatically if the server
        # replied with an error code like 404 (Not Found) or 500 (Server Error).
        response.raise_for_status()

        # .json() parses the raw JSON text in the response body into a Python dict.
        data = response.json()

        # The API returns a list under "current_condition"; [0] picks the first item.
        # List indexing is 0-based in Python: index 0 = first item.
        current = data["current_condition"][0]

        # Build and return a clean, minimal dict with only what we display.
        # int() converts strings (like "22") to integers (22) — the API returns strings.
        return {
            "city":        city,
            "temp_c":      int(current["temp_C"]),
            "feels_like":  int(current["FeelsLikeC"]),
            "description": current["weatherDesc"][0]["value"],
            "humidity":    int(current["humidity"]),
        }

    except (requests.RequestException, KeyError, json.JSONDecodeError) as err:
        # `as err` binds the exception object to the name `err` so we can log it.
        # %s in the format string is replaced by str(err) at runtime.
        # We use WARNING (not ERROR) because the program can still run without weather.
        log.warning("Weather unavailable: %s", err)
        return None   # signal "no data" to the caller without crashing


def fetch_stories(limit: int = DEFAULT_STORIES) -> list[dict]:
    """
    Fetch the top N Hacker News stories, sorted by score (highest first).

    Returns a list of dicts (possibly empty) — never returns None.
    Returning an empty list [] instead of None means callers can always do
    `for story in fetch_stories()` without checking for None first.

    `limit: int = DEFAULT_STORIES` means: limit is an int, and if the caller
    doesn't pass a value, it defaults to DEFAULT_STORIES (5).
    """

    # min(a, b) returns the smaller of two values.
    # This "clamps" the limit so a user passing --stories 999 still only gets MAX_STORIES.
    limit = min(limit, MAX_STORIES)

    try:
        response = requests.get(HN_TOP_URL, timeout=10)
        response.raise_for_status()

        # HN returns a JSON array of hundreds of IDs.
        # [:limit * 3] is a SLICE — it takes only the first (limit × 3) items.
        # We fetch 3× more IDs than we need because some stories won't have a URL
        # and we'll filter them out later.  Slice syntax: list[start:stop:step]
        # Omitting start means 0; omitting stop means end-of-list.
        top_ids = response.json()[: limit * 3]

    except requests.RequestException as err:
        log.warning("Hacker News unavailable: %s", err)
        return []   # empty list — caller's for-loop will simply not execute

    # Fetch each story's details one at a time.
    # `raw` accumulates the results; type annotation list[dict] is optional but helpful.
    raw: list[dict] = []

    for story_id in top_ids:
        # Early exit: stop fetching once we have enough candidates.
        if len(raw) >= limit:
            break

        try:
            r = requests.get(HN_ITEM_URL.format(id=story_id), timeout=10)
            r.raise_for_status()
            raw.append(r.json())   # .append() adds one item to the end of a list
        except requests.RequestException:
            # No `as err` needed here — we just skip broken items.
            # `continue` jumps to the next loop iteration immediately.
            continue

    # LIST COMPREHENSION
    # ──────────────────
    # A compact way to build a new list by filtering or transforming another list.
    #
    #   [expression  for variable in iterable  if condition]
    #
    # This line reads: "give me s, for every s in raw, but only if s has both
    # a 'title' and a 'url' key".
    #
    # dict.get("key") returns the value or None if the key is missing.
    # `if s.get("title") and s.get("url")` is True only when both are truthy (non-None, non-empty).
    valid = [s for s in raw if s.get("title") and s.get("url")]

    # sorted() returns a NEW sorted list (it doesn't modify `valid` in place).
    # key=lambda s: s.get("score", 0)  tells sorted() what value to compare.
    #   lambda is an anonymous function written inline:  lambda arguments: expression
    #   s.get("score", 0) returns the score, or 0 if the story has no score field.
    # reverse=True means highest score comes first (descending order).
    return sorted(valid, key=lambda s: s.get("score", 0), reverse=True)


def fetch_quote() -> dict | None:
    """
    Fetch a random motivational quote from zenquotes.io.

    Returns {"text": "...", "author": "..."} or None on failure.
    """
    try:
        response = requests.get(QUOTE_URL, timeout=10)
        response.raise_for_status()

        # The API returns a list with one item: [{"q": "...", "a": "..."}]
        # [0] grabs that first (and only) item.
        item = response.json()[0]

        # Return a cleaner dict with friendlier key names ("text" and "author"
        # instead of the API's cryptic "q" and "a").
        return {"text": item["q"], "author": item["a"]}

    except (requests.RequestException, KeyError, json.JSONDecodeError) as err:
        log.warning("Quote unavailable: %s", err)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# REPORT BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_report(
    weather: dict | None,   # None means the fetch failed — we handle that gracefully
    stories: list[dict],    # may be an empty list
    quote:   dict | None,
) -> str:
    """
    Combine weather, stories, and quote into a single Markdown-formatted string.

    Markdown is plain text with special symbols that render as formatted content
    in apps like GitHub, VS Code, or Obsidian:
      # Heading 1    ## Heading 2    **bold**    > blockquote
    """

    now      = datetime.now()   # current date + time as a datetime object

    # strftime("format") converts a datetime into a string using format codes:
    #   %A = full weekday name (Saturday)   %d = zero-padded day (07)
    #   %b = abbreviated month (Jun)        %Y = 4-digit year (2026)
    #   %H = 24-hour hour (07)              %M = minutes (05)
    date_str = now.strftime("%A, %d %b %Y")   # e.g. "Saturday, 07 Jun 2026"
    time_str = now.strftime("%H:%M")           # e.g. "07:05"

    # We build the report as a LIST of strings, then join them at the end.
    # This is more efficient than concatenating strings with +=, because each
    # += creates a brand-new string object in memory.
    lines: list[str] = [
        f"# Daily Briefing  —  {date_str}  ·  {time_str}",
        "",
        "## Weather",
    ]

    # F-STRINGS (formatted string literals)
    # ──────────────────────────────────────
    # Prefix a string with f"..." and you can embed any Python expression
    # inside {curly braces}.  e.g. f"Temp: {weather['temp_c']}°C"

    if weather:
        # `+=` on a list is the same as calling .extend() — it appends multiple items.
        lines += [
            f"**{weather['city']}**  —  {weather['description']}",
            f"  {weather['temp_c']}°C  (feels like {weather['feels_like']}°C)   "
            f"humidity {weather['humidity']}%",
        ]
    else:
        # Markdown: _text_ renders as italic
        lines.append("_Weather data unavailable._")

    lines += ["", "## Top Stories"]

    if stories:
        # enumerate(iterable, start=1) yields (index, value) pairs.
        # Without start=1 the index would begin at 0; we want a 1-based numbered list.
        for i, story in enumerate(stories, start=1):
            # dict.get("key", default) returns default if the key doesn't exist.
            score = story.get("score", 0)
            lines.append(f"{i}. {story['title']}  (↑{score})")
            lines.append(f"   {story['url']}")
    else:
        lines.append("_No stories available._")

    if quote:
        lines += [
            "",
            "## Quote of the Day",
            f"> {quote['text']}",    # Markdown: > text = blockquote
            f"> — {quote['author']}",
        ]

    # "\n".join(list) inserts a newline character between every item in the list
    # and returns a single string.  It's the reverse of str.split("\n").
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# FILE SAVER
# ══════════════════════════════════════════════════════════════════════════════

def save_report(content: str, output_dir: Path) -> Path:
    """
    Save the report string to  output_dir/YYYY-MM-DD.md.

    Returns the Path of the newly created file so the caller can log it.
    """

    # mkdir creates the directory.
    #   parents=True  → also create any missing parent directories
    #   exist_ok=True → don't raise an error if the directory already exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build the filename from today's date: "2026-06-07.md"
    filename = datetime.now().strftime("%Y-%m-%d") + ".md"

    # Path / "string" is a clean way to join paths (works on Windows and Mac/Linux).
    # It's equivalent to os.path.join(output_dir, filename).
    filepath = output_dir / filename

    # write_text() opens the file, writes the string, and closes it — all in one call.
    # encoding="utf-8" ensures special characters (°C, —, ↑) are saved correctly.
    filepath.write_text(content, encoding="utf-8")

    return filepath


# ══════════════════════════════════════════════════════════════════════════════
# CLI ARGUMENT PARSER
# ══════════════════════════════════════════════════════════════════════════════
#
# argparse reads sys.argv (the list of words you typed after `python main.py`)
# and converts them into a structured Namespace object with named attributes.
# Run `python main.py --help` to see the auto-generated help text.

def parse_args() -> argparse.Namespace:
    """
    Define what command-line flags the script accepts and return the parsed values.

    argparse.Namespace is just an object where each flag becomes an attribute:
      args.city      args.stories      args.no_quote      args.no_save
    """

    parser = argparse.ArgumentParser(
        description="Fetch weather, top HN stories, and a quote — then save or print.",
        # ArgumentDefaultsHelpFormatter automatically appends " (default: X)"
        # to every help string so users can see the defaults in --help.
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # add_argument() registers one CLI flag.
    # "--city" means the user types --city London  (a keyword argument).
    # default= is used when the flag is omitted entirely.
    parser.add_argument(
        "--city",
        default=DEFAULT_CITY,
        help="City name for weather lookup",
    )

    parser.add_argument(
        "--stories",
        type=int,          # argparse calls int() on the raw string for us
        default=DEFAULT_STORIES,
        metavar="N",       # replaces the placeholder in --help: "--stories N" instead of "--stories STORIES"
        help=f"Number of HN stories to include (max {MAX_STORIES})",
    )

    # store_true: if the flag is present → True, if absent → False.
    # These are boolean "switches" with no value after them.
    parser.add_argument("--no-quote", action="store_true", help="Skip the motivational quote")
    parser.add_argument("--no-save",  action="store_true", help="Print to terminal only; do not write a file")

    # type=Path tells argparse to convert the string into a Path object for us.
    parser.add_argument(
        "--output",
        type=Path,
        default=BRIEFINGS_DIR,
        help="Directory where .md briefing files are saved",
    )

    return parser.parse_args()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — the entry point that wires everything together
# ══════════════════════════════════════════════════════════════════════════════
#
# Keeping main() short means it acts like a table of contents:
# you can read it top-to-bottom to understand the whole program flow
# without getting lost in implementation details.

def main() -> None:
    """Coordinate all steps: parse args → fetch data → build report → output."""

    args = parse_args()

    log.info("Fetching weather for %s …", args.city)
    weather = fetch_weather(args.city)

    log.info("Fetching top %d Hacker News stories …", args.stories)
    stories = fetch_stories(args.stories)

    # args.no_quote is True when the user passed --no-quote.
    # `not args.no_quote` flips that: fetch a quote only when the flag was NOT given.
    quote = None
    if not args.no_quote:
        log.info("Fetching quote …")
        quote = fetch_quote()

    report = build_report(weather, stories, quote)

    # "\n" adds blank lines before and after the report for readability in the terminal.
    print("\n" + report + "\n")

    if not args.no_save:
        path = save_report(report, args.output)
        log.info("Saved → %s", path)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT GUARD
# ══════════════════════════════════════════════════════════════════════════════
#
# When Python runs a file directly (python main.py), it sets the special
# variable __name__ to the string "__main__".
#
# When another file imports this module (import main), __name__ is "main"
# and this block is SKIPPED — which is the right behaviour: importing a module
# shouldn't immediately run the whole program.

if __name__ == "__main__":
    main()
