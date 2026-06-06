# ══════════════════════════════════════════════════════════════════════════════
# WHAT IS A DOCKERFILE?
# ══════════════════════════════════════════════════════════════════════════════
#
# A Dockerfile is a recipe that tells Docker how to build a "container image".
# A container image is a self-contained, portable snapshot of an environment:
# the OS, Python, dependencies, and your code — all bundled together.
#
# Once built, the image runs the same way on any machine (your laptop, a server,
# a colleague's computer) regardless of what is installed there.
#
# BUILD the image:   docker build -t daily-briefing -f docker/Dockerfile .
# RUN  a container:  docker run --rm daily-briefing
# Pass CLI flags:    docker run --rm daily-briefing --city London --stories 7
# ══════════════════════════════════════════════════════════════════════════════


# ── STAGE: base image ─────────────────────────────────────────────────────────
#
# FROM sets the starting point for our image.
# We use the official Python image from Docker Hub (hub.docker.com/_/python).
#
#   python:3.12-slim  →  Python 3.12 on a minimal Debian Linux
#                         "slim" means no extra packages pre-installed,
#                         which keeps the image small and secure.
FROM python:3.12-slim


# ── STAGE: system hygiene ──────────────────────────────────────────────────────
#
# Set environment variables that improve Python's behaviour inside a container.
#
# PYTHONDONTWRITEBYTECODE=1
#   Stops Python from creating .pyc (compiled bytecode) files.
#   Not needed inside a container — keeps the image clean.
#
# PYTHONUNBUFFERED=1
#   Forces Python to flush stdout/stderr immediately instead of buffering.
#   Without this, log.info() messages might not appear in `docker logs`.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1


# ── STAGE: working directory ───────────────────────────────────────────────────
#
# WORKDIR sets (and creates) the directory that all subsequent commands run in.
# Think of it as `mkdir /app && cd /app` combined.
# /app is a conventional name — nothing special about it.
WORKDIR /app


# ── STAGE: install dependencies ───────────────────────────────────────────────
#
# WHY COPY requirements.txt BEFORE the source code?
#   Docker builds images in layers.  Each instruction (COPY, RUN, etc.) creates
#   a new layer that is cached.  If requirements.txt hasn't changed, Docker
#   reuses the cached pip install layer and rebuilds only what changed.
#   This makes iterative development much faster.
#
# COPY <source-on-your-machine>  <destination-in-the-image>
#   The source path is relative to the "build context" — the folder you pass
#   to `docker build`.  We pass `.` (project root), so:
#     requirements.txt  →  found at  ./requirements.txt  on your machine
#     /app/requirements.txt  →  where it lands inside the image
COPY requirements.txt .

# RUN executes a shell command during the build.
#   pip install -r requirements.txt  reads the file and installs every package.
#   --no-cache-dir  tells pip not to save downloaded packages to disk,
#                   reducing the image size.
RUN pip install --no-cache-dir -r requirements.txt


# ── STAGE: copy application code ──────────────────────────────────────────────
#
# Now copy the actual source code.  This happens AFTER pip install so that
# changing your Python code doesn't invalidate the dependency cache layer.
#
# COPY app/ /app/app/
#   Left side  (app/)       → the app/ folder on your machine
#   Right side (/app/app/)  → where it lands inside the container
#
# Result inside the container:
#   /app/
#   └── app/
#       └── main.py
COPY app/ /app/app/


# ── STAGE: default command ────────────────────────────────────────────────────
#
# CMD defines what runs when someone does `docker run <image>` with no extra arguments.
#
# We use the JSON array form (["python", "app/main.py"]) rather than a plain
# string because it skips the shell and passes arguments directly to Python.
# This means extra flags passed to `docker run` are appended correctly:
#
#   docker run --rm daily-briefing --city London
#   → runs:  python app/main.py --city London
#
# --no-save is the default because saving a file inside a container is useless
# unless you mount a volume.  Remove it if you mount /app/app/briefings.
CMD ["python", "app/main.py", "--no-save"]
