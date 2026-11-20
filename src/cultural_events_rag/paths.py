"""Where the files this package reads live: the root of the repository, two
levels above ``src/cultural_events_rag/``.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The secrets and the local settings, never committed: see .env.example.
ENV_FILE = ROOT / ".env"
