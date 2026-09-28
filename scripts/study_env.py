"""Point tau2 at the fork's data folder. Import this before any tau2 module.

tau2 finds its data through TAU2_DATA_DIR, falling back to a path inside its
own package, which does not exist when it is installed from git (see
docs/TAU2_NOTES.md Flag 7).
"""

import os
from pathlib import Path

FORK = Path(__file__).resolve().parents[2] / "tau2-bench"
os.environ.setdefault("TAU2_DATA_DIR", str(FORK / "data"))
# tau2 logs its whole registry at DEBUG level on import; keep study output clean.
os.environ.setdefault("LOGURU_LEVEL", "WARNING")
