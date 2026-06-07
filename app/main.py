"""
daily_briefing — a morning CLI briefing tool.

WHAT THIS SCRIPT DOES
─────────────────────
Every morning, run this script and it will:
  1. Fetch the current weather for a city
  2. Fetch the top stories from Hacker News
  3. Fetch a random inspirational quote
  4. Print a pretty, coloured report in the terminal
  5. Optionally save the report as a Markdown file

HOW TO RUN IT
─────────────
  python main.py                           # defaults: London, 5 stories, with quote, save file
  python main.py --city "New York"         # change the city
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

import argparse  # stdlib: reads command-line flags like --city London
import json  # stdlib: converts JSON text ↔ Python dicts/lists
import logging  # stdlib: structured status messages (better than print)
from datetime import datetime  # stdlib: work with dates and times
from pathlib import Path  # stdlib: handle file paths in a cross-platform way

import requests  # third-party: make HTTP requests    (pip install requests)
from rich import box  # pre-defined border styles for panels

# rich is a third-party library for beautiful terminal output.
# It can print coloured text, tables, panels, progress bars, and more.
from rich.console import Console  # the main object that prints styled text
from rich.panel import Panel  # a box drawn around content with a title
from rich.rule import Rule  # a horizontal dividing line
from rich.text import Text  # a string that can have per-character styles

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
#
# Constants are variables whose values never change while the program runs.
# Python convention: write them in UPPER_SNAKE_CASE so readers know at a glance
# they aren't meant to be modified.

DEFAULT_CITY = "London"
DEFAULT_STORIES = 5
MAX_STORIES = 10

# Path(__file__) → the path of THIS file (main.py)
# .parent        → the folder that contains main.py  (i.e. app/)
# / "briefings"  → the sub-folder where we save reports
BRIEFINGS_DIR = Path(__file__).parent / "briefings"

# API URLs — {city} and {id} are placeholders filled in later with .format()
WEATHER_URL = "https://wttr.in/{city}?format=j1"
HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

# dummyjson.com is a free, reliable API with no SSL certificate issues.
# It returns: {"id": 1, "quote": "...", "author": "..."}
QUOTE_URL = "https://dummyjson.com/quotes/random"

# Weather condition keywords → (emoji, rich colour name)
# We scan the description text for these keywords and pick a matching style.
WEATHER_STYLES: list[tuple[str, str, str]] = [
    ("sunny", "☀️", "yellow"),
    ("clear", "🌤️", "yellow"),
    ("cloud", "☁️", "white"),
    ("overcast", "☁️", "white"),
    ("rain", "🌧️", "blue"),
    ("drizzle", "🌦️", "blue"),
    ("snow", "❄️", "cyan"),
    ("thunder", "⛈️", "red"),
    ("fog", "🌫️", "white"),
    ("mist", "🌫️", "white"),
]


# ══════════════════════════════════════════════════════════════════════════════
# CONSOLE + LOGGING SETUP
# ══════════════════════════════════════════════════════════════════════════════

# Console() is the rich object we call to print styled output.
# stderr=True sends log-style messages to stderr (the "error" stream) so they
# don't mix with the actual report if someone redirects stdout to a file.
console = Console()
log_console = Console(stderr=True, style="dim")

# We use standard logging only for WARNING and above (e.g. network failures).
# INFO messages are printed directly via log_console for nicer formatting.
logging.basicConfig(level=logging.WARNING, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════


def weather_style(description: str) -> tuple[str, str]:
    """
    Given a weather description like "Sunny" return (emoji, colour).

    str.lower() makes the comparison case-insensitive so "Sunny" and "sunny"
    both match. We iterate over WEATHER_STYLES until we find a keyword that
    appears anywhere in the description.
    """
    desc_lower = description.lower()
    for keyword, emoji, colour in WEATHER_STYLES:
        if keyword in desc_lower:
            return emoji, colour
    return "🌡️", "white"  # fallback if no keyword matched


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
    url = WEATHER_URL.format(city=city.replace(" ", "+"))

    # TRY / EXCEPT — error handling
    # ───────────────────────────────
    # Code inside `try` runs normally.
    # If an exception (error) is raised, Python jumps to the matching `except` block.
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
            "city": city,
            "temp_c": int(current["temp_C"]),
            "feels_like": int(current["FeelsLikeC"]),
            "description": current["weatherDesc"][0]["value"],
            "humidity": int(current["humidity"]),
        }

    except (requests.RequestException, KeyError, json.JSONDecodeError) as err:
        log.warning("Weather unavailable: %s", err)
        return None


def fetch_stories(limit: int = DEFAULT_STORIES) -> list[dict]:
    """
    Fetch the top N Hacker News stories, sorted by score (highest first).

    Returns a list of dicts (possibly empty) — never returns None.
    Returning an empty list [] instead of None means callers can always do
    `for story in fetch_stories()` without checking for None first.
    """

    # min(a, b) returns the smaller of two values.
    # This "clamps" the limit so a user passing --stories 999 still only gets MAX_STORIES.
    limit = min(limit, MAX_STORIES)

    try:
        response = requests.get(HN_TOP_URL, timeout=10)
        response.raise_for_status()

        # [:limit * 3] is a SLICE — takes only the first (limit × 3) items.
        # We fetch 3× more IDs than we need because some stories won't have a URL.
        top_ids = response.json()[: limit * 3]

    except requests.RequestException as err:
        log.warning("Hacker News unavailable: %s", err)
        return []

    raw: list[dict] = []

    for story_id in top_ids:
        if len(raw) >= limit:
            break  # stop fetching as soon as we have enough candidates
        try:
            r = requests.get(HN_ITEM_URL.format(id=story_id), timeout=10)
            r.raise_for_status()
            raw.append(r.json())  # .append() adds one item to the end of the list
        except requests.RequestException:
            continue  # skip broken items and keep going

    # LIST COMPREHENSION — a compact way to build a filtered list in one line.
    # Read as: "give me s for every s in raw, but only if s has title AND url"
    valid = [s for s in raw if s.get("title") and s.get("url")]

    # sorted() returns a new sorted list.
    # key=lambda s: ... tells it what value to sort by.
    # reverse=True → highest score first (descending order).
    return sorted(valid, key=lambda s: s.get("score", 0), reverse=True)


def fetch_quote() -> dict | None:
    """
    Fetch a random quote from dummyjson.com.

    Returns {"text": "...", "author": "..."} or None on failure.
    The dummyjson API response looks like: {"id": 1, "quote": "...", "author": "..."}
    """
    try:
        response = requests.get(QUOTE_URL, timeout=10)
        response.raise_for_status()
        item = response.json()  # a single dict (not a list)
        return {"text": item["quote"], "author": item["author"]}
    except (requests.RequestException, KeyError, json.JSONDecodeError) as err:
        log.warning("Quote unavailable: %s", err)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# DISPLAY — functions that print to the terminal using rich
# ══════════════════════════════════════════════════════════════════════════════
#
# rich lets you embed markup inside strings:
#   [bold]text[/bold]   [green]text[/green]   [bold cyan]text[/]
# The Console object interprets these tags and applies the matching ANSI codes.


def print_report(
    weather: dict | None,
    stories: list[dict],
    quote: dict | None,
) -> None:
    """Print a beautifully formatted briefing to the terminal using rich."""

    now = datetime.now()
    date_str = now.strftime("%A, %d %b %Y")  # e.g. "Saturday, 07 Jun 2026"
    time_str = now.strftime("%H:%M")  # e.g. "07:05"

    console.print()  # blank line for breathing room

    # ── Header ────────────────────────────────────────────────────────────────
    # Rule() draws a full-width horizontal line with optional centred text.
    console.print(
        Rule(
            f"[bold white] Daily Briefing  ·  {date_str}  ·  {time_str} [/]",
            style="bright_black",
        )
    )
    console.print()

    # ── Weather ───────────────────────────────────────────────────────────────
    if weather:
        emoji, colour = weather_style(weather["description"])

        # Text() lets us build a string with mixed styles.
        # .append(text, style=...) adds a chunk with the given style.
        weather_text = Text()
        weather_text.append(
            f"  {emoji}  {weather['description']}\n\n", style=f"bold {colour}"
        )
        weather_text.append(f"  🌡️  {weather['temp_c']}°C", style="bold white")
        weather_text.append(
            f"  (feels like {weather['feels_like']}°C)\n", style="white"
        )
        weather_text.append(f"  💧 Humidity {weather['humidity']}%", style="white")

        console.print(
            Panel(
                weather_text,
                title=f"[bold cyan]📍 {weather['city']}[/]",
                border_style="cyan",
                box=box.ROUNDED,
                padding=(0, 2),
            )
        )
    else:
        console.print(
            Panel(
                "[dim]Weather data unavailable.[/]",
                title="Weather",
                border_style="bright_black",
            )
        )

    console.print()

    # ── Top Stories ───────────────────────────────────────────────────────────
    if stories:
        # Build the stories text block item by item.
        stories_text = Text()
        for i, story in enumerate(stories, start=1):
            score = story.get("score", 0)

            # Each story: bold number, title, then score and URL on separate lines.
            stories_text.append(f"  {i}. ", style="bold bright_black")
            stories_text.append(f"{story['title']}", style="bold white")
            stories_text.append(f"  ↑{score}\n", style="green")
            stories_text.append(f"     {story['url']}\n", style="dim blue underline")

            # Add a blank line between stories but not after the last one.
            if i < len(stories):
                stories_text.append("\n")

        console.print(
            Panel(
                stories_text,
                title="[bold yellow]🔥 Top Hacker News Stories[/]",
                border_style="yellow",
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )
    else:
        console.print(
            Panel(
                "[dim]No stories available.[/]",
                title="Top Stories",
                border_style="bright_black",
            )
        )

    # ── Quote ─────────────────────────────────────────────────────────────────
    if quote:
        console.print()
        quote_text = Text()
        quote_text.append(f'  "{quote["text"]}"', style="italic white")
        quote_text.append(f"\n\n  — {quote['author']}", style="bold bright_black")

        console.print(
            Panel(
                quote_text,
                title="[bold magenta]✨ Quote of the Day[/]",
                border_style="magenta",
                box=box.ROUNDED,
                padding=(0, 2),
            )
        )

    console.print()


# ══════════════════════════════════════════════════════════════════════════════
# MARKDOWN REPORT BUILDER — for saving to a file
# ══════════════════════════════════════════════════════════════════════════════


def build_markdown(
    weather: dict | None,
    stories: list[dict],
    quote: dict | None,
) -> str:
    """
    Assemble all sections into one Markdown string (for the saved .md file).

    The terminal uses rich for pretty output; the file uses plain Markdown
    so it renders nicely in GitHub, VS Code, Obsidian, etc.
    """

    now = datetime.now()
    date_str = now.strftime("%A, %d %b %Y")
    time_str = now.strftime("%H:%M")

    # Build a list of lines, then join them at the end.
    # This is faster and cleaner than concatenating strings with +=.
    lines: list[str] = [
        f"# Daily Briefing  —  {date_str}  ·  {time_str}",
        "",
        "## Weather",
    ]

    if weather:
        lines += [
            f"**{weather['city']}**  —  {weather['description']}",
            f"  {weather['temp_c']}°C  (feels like {weather['feels_like']}°C)   "
            f"humidity {weather['humidity']}%",
        ]
    else:
        lines.append("_Weather data unavailable._")

    lines += ["", "## Top Stories"]

    if stories:
        # enumerate(iterable, start=1) gives (index, value) pairs starting at 1.
        for i, story in enumerate(stories, start=1):
            score = story.get("score", 0)
            lines.append(f"{i}. {story['title']}  (↑{score})")
            lines.append(f"   {story['url']}")
    else:
        lines.append("_No stories available._")

    if quote:
        lines += [
            "",
            "## Quote of the Day",
            f"> {quote['text']}",
            f"> — {quote['author']}",
        ]

    # "\n".join(list) merges all lines with a newline between each.
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# FILE SAVER
# ══════════════════════════════════════════════════════════════════════════════


def save_report(content: str, output_dir: Path) -> Path:
    """
    Write the Markdown report to  output_dir/YYYY-MM-DD.md.

    Returns the Path of the newly created file so the caller can log it.
    """

    # mkdir creates the directory.
    #   parents=True  → also create any missing parent directories
    #   exist_ok=True → don't raise an error if the directory already exists
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = datetime.now().strftime("%Y-%m-%d") + ".md"

    # Path / "string" is a clean way to join paths (works on Windows and Mac/Linux).
    filepath = output_dir / filename

    # write_text() opens the file, writes the string, and closes it — all in one call.
    # encoding="utf-8" ensures special characters (°C, —, ↑) are saved correctly.
    filepath.write_text(content, encoding="utf-8")

    return filepath


# ══════════════════════════════════════════════════════════════════════════════
# CLI ARGUMENT PARSER
# ══════════════════════════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    """
    Define what command-line flags the script accepts and return the parsed values.

    Run `python main.py --help` to see the auto-generated help text.
    """

    parser = argparse.ArgumentParser(
        description="Fetch weather, top HN stories, and a quote — then display or save.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--city", default=DEFAULT_CITY, help="City name for weather lookup"
    )
    parser.add_argument(
        "--stories",
        type=int,
        default=DEFAULT_STORIES,
        metavar="N",
        help=f"Number of HN stories to include (max {MAX_STORIES})",
    )
    parser.add_argument(
        "--no-quote", action="store_true", help="Skip the motivational quote"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print to terminal only; do not write a file",
    )
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


def main() -> None:
    """Coordinate all steps: parse args → fetch data → display → save."""

    args = parse_args()

    log_console.print(f"  Fetching weather for [bold]{args.city}[/] …")
    weather = fetch_weather(args.city)

    log_console.print(f"  Fetching top [bold]{args.stories}[/] Hacker News stories …")
    stories = fetch_stories(args.stories)

    # args.no_quote is True when the user passed --no-quote.
    # `not args.no_quote` flips that: fetch a quote only when the flag was NOT given.
    quote = None
    if not args.no_quote:
        log_console.print("  Fetching quote …")
        quote = fetch_quote()

    # Print the rich terminal display.
    print_report(weather, stories, quote)

    if not args.no_save:
        markdown = build_markdown(weather, stories, quote)
        path = save_report(markdown, args.output)
        console.print(f"[dim]  Saved → {path}[/]\n")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT GUARD
# ══════════════════════════════════════════════════════════════════════════════
#
# When Python runs a file directly (python main.py), it sets __name__ = "__main__".
# When another file imports this module, __name__ = "main" and this block is skipped.

if __name__ == "__main__":
    main()
