"""The paths of the files the package reads and writes, from the root of the
repository."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The local settings and secrets, not versioned.
ENV_FILE = ROOT / ".env"

# The raw events, one file per source, not versioned.
RAW_DIR = ROOT / "data" / "raw"

# The events of the common format, one per line, not versioned.
PROCESSED_DIR = ROOT / "data" / "processed"
EVENTS_FILE = PROCESSED_DIR / "events.jsonl"

# The benchmark, versioned: the annotated questions and the frozen events they
# were judged on.
BENCHMARK_DIR = ROOT / "data" / "benchmark"
BENCHMARK_QUESTIONS = BENCHMARK_DIR / "questions.json"
BENCHMARK_EVENTS = BENCHMARK_DIR / "events.jsonl"

# The reports of the evaluations, versioned.
REPORTS_DIR = ROOT / "reports"
