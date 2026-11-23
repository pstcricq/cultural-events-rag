"""Where the files this package reads live: the root of the repository, two
levels above ``src/cultural_events_rag/``.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The secrets and the local settings, never committed: see .env.example.
ENV_FILE = ROOT / ".env"

# The events as each API returns them, one file per source, never committed.
RAW_DIR = ROOT / "data" / "raw"

# The events of the common format, one per line, never committed.
PROCESSED_DIR = ROOT / "data" / "processed"
EVENTS_FILE = PROCESSED_DIR / "events.jsonl"

# The benchmark, committed: the annotated questions, and the events they were
# judged on, frozen.
BENCHMARK_DIR = ROOT / "data" / "benchmark"
BENCHMARK_QUESTIONS = BENCHMARK_DIR / "questions.json"
BENCHMARK_EVENTS = BENCHMARK_DIR / "events.jsonl"

# The reports of the evaluations, committed: their history shows the effect of
# each change.
REPORTS_DIR = ROOT / "reports"
