"""Stage 5 analysis of the main runs (docs/EXPERIMENT_PLAN.md Section 6).

The analysis reuses study scripts (task specs, the Stage 3.3 language
detection), so the scripts folder goes on the import path here, as
`pyproject.toml` does for the tests.
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
