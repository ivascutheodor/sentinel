from pathlib import Path

# Where the worker writes clips (and `manifests/`), and what the API serves from. The
# backend must run on the machine that holds this folder.
RECORDINGS_DIR = Path(__file__).resolve().parents[3] / "recordings"
