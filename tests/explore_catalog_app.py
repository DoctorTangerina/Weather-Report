"""Catalog browser fixture: a real seed copy with one unavailable Variable.

Only the temporary copy omits Amazon vegetation. The committed seed and the
other browser harnesses keep all their data; HTTP responses are never mocked.
"""

import shutil
import tempfile
from pathlib import Path

from api import main
from engine import ENGINE_VERSION, JsonResultStore

workspace = tempfile.TemporaryDirectory(prefix="weather-explore-catalog-")
seed = Path(workspace.name) / "seed"
shutil.copytree(
    main.DATA_DIR,
    seed,
    ignore=shutil.ignore_patterns("amazon-basin__vegetation-index.json"),
)
main.store = JsonResultStore(seed, ENGINE_VERSION)
app = main.app
