import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/research-workbench-verifier-mpl")
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
